"""补货决策业务：策略 CRUD、动态 SS/ROP 建议生成、一键转请购单。

口径（M6 定稿，见 docs/db-schema.md §12.5/§12.6、ADR-0002）：
- 服务水平 CSL，z=Φ⁻¹(CSL)（无 scipy 依赖，用 Acklam 近似）；
  SS = z·√(LT·σD² + D̂²·σLT²)，ROP = D̂·LT + SS，S = ROP + D̂·复核周期。
- 触发：库存位置 IP = 结存 − 锁定 + 在途 ≤ ROP 才生成 OPEN 建议（未触发不落库）。
- 下单量：qty = S − IP，按 min_order_qty/pack_size 向上取整；EOQ 仅作参考量。
- 建议须人工确认（OPEN→SUGGESTED，可改 final_qty）后才能一键转请购单；
  转单生成 DRAFT 请购单并写 converted_pr_id/converted_at 来源链。
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.core.errors import BadRequest, Conflict, NotFound
from app.model.base import utcnow
from app.model.replenishment import ReplenishmentPolicy, ReplenishmentSuggestion
from app.repository.forecast import DemandSeriesMetaRepo, ForecastResultRepo
from app.repository.inventory import InventoryRepo
from app.repository.ledger import MaterialSupplierPriceRepo
from app.repository.master import MaterialRepo, WarehouseRepo
from app.repository.purchase import POItemRepo
from app.repository.replenishment import ReplenishmentPolicyRepo, ReplenishmentSuggestionRepo
from app.schema.purchase import PRCreate, PRItemIn
from app.service.purchase import PurchaseRequisitionService

_Q4 = Decimal("0.0001")
_ZERO = Decimal("0")
_ONE = Decimal("1")
_DEFAULT_CSL = Decimal("0.95")

# Peter Acklam 的 inverse normal CDF 近似（避免为此引入 scipy）
_PPF_A = (
    -3.969683028665376e01,
    2.209460984245205e02,
    -2.759285104469687e02,
    1.383577518672690e02,
    -3.066479806614716e01,
    2.506628277459239e00,
)
_PPF_B = (
    -5.447609879822406e01,
    1.615858368580409e02,
    -1.556989798598866e02,
    6.680131188771972e01,
    -1.328068155288572e01,
)
_PPF_C = (
    -7.784894002430293e-03,
    -3.223964580411365e-01,
    -2.400758277161838e00,
    -2.549732539343734e00,
    4.374664141464968e00,
    2.938163982698783e00,
)
_PPF_D = (
    7.784695709041462e-03,
    3.224671290700398e-01,
    2.445134137142996e00,
    3.754408661907416e00,
)
_P_LOW = 0.02425
_P_HIGH = 1.0 - _P_LOW


def norm_ppf(p: float) -> float:
    """标准正态分布分位数 Φ⁻¹(p)（Acklam 近似，精度 ~1e-9）。"""
    if not 0.0 < p < 1.0:
        raise ValueError("p 必须在 (0,1) 内")
    if p < _P_LOW:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((_PPF_C[0] * q + _PPF_C[1]) * q + _PPF_C[2]) * q + _PPF_C[3]) * q + _PPF_C[4]) * q + _PPF_C[5]) / (
            (((_PPF_D[0] * q + _PPF_D[1]) * q + _PPF_D[2]) * q + _PPF_D[3]) * q + 1.0
        )
    if p <= _P_HIGH:
        q = p - 0.5
        r = q * q
        return (
            (((((_PPF_A[0] * r + _PPF_A[1]) * r + _PPF_A[2]) * r + _PPF_A[3]) * r + _PPF_A[4]) * r + _PPF_A[5])
            * q
            / (((((_PPF_B[0] * r + _PPF_B[1]) * r + _PPF_B[2]) * r + _PPF_B[3]) * r + _PPF_B[4]) * r + 1.0)
        )
    q = math.sqrt(-2.0 * math.log(1.0 - p))
    return -(((((_PPF_C[0] * q + _PPF_C[1]) * q + _PPF_C[2]) * q + _PPF_C[3]) * q + _PPF_C[4]) * q + _PPF_C[5]) / (
        (((_PPF_D[0] * q + _PPF_D[1]) * q + _PPF_D[2]) * q + _PPF_D[3]) * q + 1.0
    )


def _dec(value, default: Decimal = _ZERO) -> Decimal:
    if value is None:
        return default
    return Decimal(str(value))


def _q4(value) -> Decimal:
    return Decimal(str(value)).quantize(_Q4, rounding=ROUND_HALF_UP)


def _round_order_qty(quantity: Decimal, min_order_qty: Decimal, pack_size: Decimal) -> Decimal:
    """按起订量下限 + 包装倍数向上取整。"""
    pack = pack_size if pack_size and pack_size > 0 else _ONE
    floor = min_order_qty if min_order_qty and min_order_qty > 0 else _ZERO
    qty = quantity if quantity > floor else floor
    if qty <= 0:
        return _ZERO
    steps = (qty / pack).to_integral_value(rounding=ROUND_CEILING)
    return (steps * pack).quantize(_Q4, rounding=ROUND_HALF_UP)


def _f(value) -> str:
    return ("%.3f" % float(value)).rstrip("0").rstrip(".")


class ReplenishmentPolicyService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ReplenishmentPolicyRepo(db)

    def list(
        self,
        page: int,
        page_size: int,
        material_id: int | None = None,
        warehouse_id: int | None = None,
        is_active: bool | None = None,
    ):
        return self.repo.list((page - 1) * page_size, page_size, material_id, warehouse_id, is_active)

    def get(self, policy_id: int) -> ReplenishmentPolicy:
        obj = self.repo.get_active(policy_id)
        if obj is None:
            raise NotFound("补货策略不存在")
        return obj

    def create(self, payload, operator_id: int) -> ReplenishmentPolicy:
        if self.repo.find_by_code(payload.policy_code) is not None:
            raise Conflict("策略编码已存在：" + payload.policy_code)
        self._require_refs(payload.material_id, payload.warehouse_id)
        obj = ReplenishmentPolicy(**payload.model_dump(), created_by=operator_id)
        self.repo.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, policy_id: int, payload) -> ReplenishmentPolicy:
        obj = self.get(policy_id)
        data = payload.model_dump(exclude_unset=True)
        if "material_id" in data or "warehouse_id" in data:
            self._require_refs(
                data.get("material_id", obj.material_id), data.get("warehouse_id", obj.warehouse_id)
            )
        for field, value in data.items():
            setattr(obj, field, value)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, policy_id: int) -> None:
        obj = self.get(policy_id)
        obj.deleted_at = utcnow()
        self.db.commit()

    def _require_refs(self, material_id: int | None, warehouse_id: int | None) -> None:
        if material_id is not None and MaterialRepo(self.db).get_active(material_id) is None:
            raise BadRequest("物资不存在：" + str(material_id))
        if warehouse_id is not None and WarehouseRepo(self.db).get_active(warehouse_id) is None:
            raise BadRequest("仓库不存在：" + str(warehouse_id))


class ReplenishmentSuggestionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ReplenishmentSuggestionRepo(db)
        self.policies = ReplenishmentPolicyRepo(db)
        self.inventory = InventoryRepo(db)
        self.forecasts = ForecastResultRepo(db)
        self.meta = DemandSeriesMetaRepo(db)

    # ---------- 查询 ----------
    def list(
        self,
        page: int,
        page_size: int,
        status: str | None = None,
        material_id: int | None = None,
        warehouse_id: int | None = None,
        trigger_type: str | None = None,
    ):
        return self.repo.list(
            (page - 1) * page_size, page_size, status, material_id, warehouse_id, trigger_type
        )

    def get(self, suggestion_id: int) -> ReplenishmentSuggestion:
        obj = self.repo.get_active(suggestion_id)
        if obj is None:
            raise NotFound("补货建议不存在")
        return obj

    # ---------- 生成 ----------
    def generate(
        self,
        operator_id: int | None,
        material_id: int | None = None,
        warehouse_id: int | None = None,
    ) -> dict:
        inventory_rows = self.inventory.list(0, 1_000_000, material_id, warehouse_id)[0]
        in_transit = POItemRepo(self.db).in_transit_by_material()
        forecasts = self.forecasts.latest_by_pair()
        meta_by_pair = self.meta.by_pairs()
        materials = {m.id: m for m in MaterialRepo(self.db).list(0, 1_000_000)[0]}
        counts = {"scanned": 0, "created": 0, "updated": 0, "closed": 0, "skipped_no_policy": 0}

        for inv in inventory_rows:
            policy = self.policies.resolve(inv.material_id, inv.warehouse_id)
            if policy is None:
                counts["skipped_no_policy"] += 1
                continue
            counts["scanned"] += 1
            material = materials.get(inv.material_id)
            forecast = forecasts.get((inv.material_id, inv.warehouse_id)) or forecasts.get(
                (inv.material_id, None)
            )
            dhat = _dec(forecast["avg"]) if forecast else _ZERO
            run_id = forecast["run_id"] if forecast else None
            model_code = forecast["model_code"] if forecast else None
            meta = meta_by_pair.get((inv.material_id, inv.warehouse_id)) or meta_by_pair.get(
                (inv.material_id, None)
            )
            sigma_d = _dec(meta.std_daily) if meta is not None and meta.std_daily is not None else _ZERO
            sigma_lt = _ZERO  # 库内暂无提前期波动数据，公式第二项退化为 0
            lead_time = (
                _dec(policy.lead_time_days)
                if policy.lead_time_days is not None
                else _dec(material.lead_time_days if material is not None else None)
            )
            z_value = self._z_for(policy)
            safety = self._safety_stock(dhat, sigma_d, lead_time, sigma_lt, z_value)
            rop = self._reorder_point(dhat, lead_time, safety)
            review = _dec(policy.review_period_days)
            order_up_to = rop + dhat * review
            eoq_value = self._eoq(inv.material_id, dhat, policy)

            current = _dec(inv.quantity)
            locked = _dec(inv.locked_qty)
            transit = _dec(in_transit.get(inv.material_id, _ZERO))
            available = current - locked + transit
            existing = self.repo.find_open(inv.material_id, inv.warehouse_id)

            triggered = available <= rop
            raw_qty = (order_up_to - available) if triggered else _ZERO
            if raw_qty <= 0:
                triggered = False

            if not triggered:
                if existing is not None and existing.status == "OPEN":
                    existing.status = "CLOSED"
                    existing.remark = "重算后可用量高于 ROP，库存充足"
                    counts["closed"] += 1
                continue

            suggested = _round_order_qty(raw_qty, _dec(policy.min_order_qty), _dec(policy.pack_size))
            if suggested <= 0:
                continue
            reason = self._reason(
                policy, inv.material_id, model_code, run_id, dhat, lead_time, sigma_d, sigma_lt,
                safety, rop, order_up_to, current, locked, transit, available, suggested,
            )
            fields = dict(
                policy_id=policy.id,
                forecast_run_id=run_id,
                trigger_type="BELOW_ROP",
                current_qty=current,
                locked_qty=locked,
                in_transit_qty=transit,
                available_qty=available,
                daily_demand_hat=dhat,
                lead_time_days=lead_time,
                sigma_d=sigma_d,
                sigma_lt=sigma_lt,
                safety_stock=safety,
                rop=rop,
                eoq=eoq_value,
                suggested_qty=suggested,
                reason=reason,
                generated_at=utcnow(),
            )
            if existing is not None:
                for field, value in fields.items():
                    setattr(existing, field, value)
                counts["updated"] += 1
            else:
                obj = ReplenishmentSuggestion(
                    suggestion_no=self.repo.next_suggestion_no(),
                    material_id=inv.material_id,
                    warehouse_id=inv.warehouse_id,
                    status="OPEN",
                    created_by=operator_id,
                    **fields,
                )
                self.repo.add(obj)
                counts["created"] += 1

        self.db.commit()
        return counts

    # ---------- 人工确认 / 驳回 ----------
    def confirm(self, suggestion_id: int, payload, operator_id: int) -> ReplenishmentSuggestion:
        obj = self.get(suggestion_id)
        if obj.status != "OPEN":
            raise Conflict("仅 OPEN 状态的建议可确认，当前：" + obj.status)
        qty = payload.final_qty if payload.final_qty is not None else obj.suggested_qty
        if qty is None or qty <= 0:
            raise BadRequest("确认数量必须大于 0")
        obj.status = "SUGGESTED"
        obj.final_qty = qty
        obj.handled_by = operator_id
        if payload.remark:
            obj.remark = payload.remark
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def reject(self, suggestion_id: int, payload, operator_id: int) -> ReplenishmentSuggestion:
        obj = self.get(suggestion_id)
        if obj.status not in ("OPEN", "SUGGESTED"):
            raise Conflict("仅 OPEN/SUGGESTED 状态的建议可驳回，当前：" + obj.status)
        obj.status = "REJECTED"
        obj.handled_by = operator_id
        if payload.reason:
            obj.remark = payload.reason
        self.db.commit()
        self.db.refresh(obj)
        return obj

    # ---------- 一键转请购单 ----------
    def convert(self, suggestion_id: int, operator_id: int):
        suggestion = self.get(suggestion_id)
        pr = self._convert_one(suggestion, operator_id)
        self.db.commit()
        self.db.refresh(suggestion)
        return suggestion, pr

    def convert_batch(self, suggestion_ids: list[int], operator_id: int):
        unique_ids = list(dict.fromkeys(suggestion_ids))
        suggestions = [self.get(sid) for sid in unique_ids]
        for suggestion in suggestions:
            self._require_convertible(suggestion)
        results = []
        for suggestion in suggestions:
            pr = self._convert_one(suggestion, operator_id)
            results.append(
                {
                    "suggestion_id": suggestion.id,
                    "suggestion_no": suggestion.suggestion_no,
                    "status": suggestion.status,
                    "converted_pr_id": suggestion.converted_pr_id,
                    "pr_doc_no": pr.doc_no,
                }
            )
        self.db.commit()
        return results

    def _require_convertible(self, suggestion: ReplenishmentSuggestion) -> None:
        if suggestion.status == "OPEN":
            raise Conflict("请先确认建议（final_qty）后再转请购单：" + suggestion.suggestion_no)
        if suggestion.status != "SUGGESTED":
            raise Conflict("仅 SUGGESTED 状态的建议可转请购单，当前：" + suggestion.status)

    def _convert_one(self, suggestion: ReplenishmentSuggestion, operator_id: int):
        self._require_convertible(suggestion)
        qty = suggestion.final_qty if suggestion.final_qty is not None else suggestion.suggested_qty
        if qty is None or qty <= 0:
            raise BadRequest("建议数量必须大于 0")
        expected_date = None
        if suggestion.lead_time_days is not None and suggestion.lead_time_days > 0:
            expected_date = date.today() + timedelta(days=int(math.ceil(float(suggestion.lead_time_days))))
        payload = PRCreate(
            title="补货建议 %s" % suggestion.suggestion_no,
            expected_date=expected_date,
            reason="由补货建议 %s 转入" % suggestion.suggestion_no,
            items=[PRItemIn(material_id=suggestion.material_id, quantity=qty, purpose="补货")],
        )
        pr_service = PurchaseRequisitionService(self.db)
        pr = pr_service.build(payload, operator_id)
        pr_service.repo.add(pr)
        suggestion.status = "CONVERTED"
        suggestion.converted_pr_id = pr.id
        suggestion.converted_at = utcnow()
        suggestion.handled_by = operator_id
        return pr

    # ---------- 计算 ----------
    def _z_for(self, policy: ReplenishmentPolicy) -> Decimal:
        if policy.z_value is not None:
            return _dec(policy.z_value)
        level = _dec(policy.service_level, _DEFAULT_CSL)
        if not (_ZERO < level < _ONE):
            level = _DEFAULT_CSL
        return _q4(Decimal(str(norm_ppf(float(level)))))

    def _safety_stock(self, dhat, sigma_d, lead_time, sigma_lt, z_value) -> Decimal:
        variance = (
            float(lead_time) * float(sigma_d) ** 2 + float(dhat) ** 2 * float(sigma_lt) ** 2
        )
        ss = float(z_value) * math.sqrt(max(variance, 0.0))
        return _q4(ss)

    def _reorder_point(self, dhat, lead_time, safety) -> Decimal:
        return _q4(dhat * lead_time + safety)

    def _eoq(self, material_id: int, dhat, policy: ReplenishmentPolicy) -> Decimal:
        """EOQ 参考量 Q* = sqrt(2·D_year·S / H)；H<=0 或 D=0 时退化为 0。"""
        order_cost = _dec(policy.order_cost)
        rate = _dec(policy.holding_cost_rate)
        annual = dhat * Decimal("365")
        if order_cost <= 0 or rate <= 0 or annual <= 0:
            return _ZERO
        prices = MaterialSupplierPriceRepo(self.db).list_preferred(material_id)
        unit_price = _dec(prices[0].unit_price if prices else _ZERO)
        unit_holding = unit_price * rate
        if unit_holding <= 0:
            return _q4(annual / Decimal("2"))
        return _q4(Decimal(str(math.sqrt(2.0 * float(annual) * float(order_cost) / float(unit_holding)))))

    def _reason(
        self, policy, material_id, model_code, run_id, dhat, lead_time, sigma_d, sigma_lt,
        safety, rop, order_up_to, current, locked, transit, available, suggested,
    ) -> str:
        return (
            "预测驱动：D^={dhat}/日，LT={lt} 天，σD={sd}，σLT={slt}；"
            "SS=z·√(LT·σD²+D^²·σLT²)={ss}，ROP=D^·LT+SS={rop}，S=ROP+D^·复核周期={s}；"
            "可用=结存 {cur}+在途 {tra}−锁定 {loc}={avail} ≤ ROP={rop}，"
            "建议订货把库存位置抬到 S，数量={qty}（已按起订量/包装取整）；"
            "参数来源：policy={pc}({strategy})，forecast_run={run}，model={model}"
        ).format(
            dhat=_f(dhat),
            lt=_f(lead_time),
            sd=_f(sigma_d),
            slt=_f(sigma_lt),
            ss=_f(safety),
            rop=_f(rop),
            s=_f(order_up_to),
            cur=_f(current),
            tra=_f(transit),
            loc=_f(locked),
            avail=_f(available),
            qty=_f(suggested),
            pc=policy.policy_code,
            strategy=policy.strategy,
            run=run_id if run_id is not None else "-",
            model=model_code or "-",
        )
