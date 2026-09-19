"""补货策略与建议数据访问。"""

from datetime import date

from sqlalchemy import and_, func, or_, select

from app.model.replenishment import ReplenishmentPolicy, ReplenishmentSuggestion

_OPEN_STATUSES = ("OPEN", "SUGGESTED")


class ReplenishmentPolicyRepo:
    def __init__(self, db) -> None:
        self.db = db

    def get_active(self, policy_id: int):
        obj = self.db.get(ReplenishmentPolicy, policy_id)
        if obj is None or obj.deleted_at is not None:
            return None
        return obj

    def add(self, obj):
        self.db.add(obj)
        self.db.flush()
        return obj

    def find_by_code(self, policy_code: str, exclude_id: int | None = None):
        stmt = select(ReplenishmentPolicy).where(
            ReplenishmentPolicy.policy_code == policy_code,
            ReplenishmentPolicy.deleted_at.is_(None),
        )
        if exclude_id is not None:
            stmt = stmt.where(ReplenishmentPolicy.id != exclude_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list(
        self,
        offset: int,
        limit: int,
        material_id: int | None = None,
        warehouse_id: int | None = None,
        is_active: bool | None = None,
    ):
        stmt = select(ReplenishmentPolicy).where(ReplenishmentPolicy.deleted_at.is_(None))
        if material_id is not None:
            stmt = stmt.where(ReplenishmentPolicy.material_id == material_id)
        if warehouse_id is not None:
            stmt = stmt.where(ReplenishmentPolicy.warehouse_id == warehouse_id)
        if is_active is not None:
            stmt = stmt.where(ReplenishmentPolicy.is_active.is_(is_active))
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        rows = self.db.execute(stmt.order_by(ReplenishmentPolicy.id.desc()).offset(offset).limit(limit)).scalars().all()
        return list(rows), int(total)

    def resolve(self, material_id: int, warehouse_id: int):
        """按 material+warehouse > material > warehouse > 全局 取最具体的启用策略。"""
        pair = and_(
            ReplenishmentPolicy.material_id == material_id,
            ReplenishmentPolicy.warehouse_id == warehouse_id,
        )
        material_wide = and_(
            ReplenishmentPolicy.material_id == material_id, ReplenishmentPolicy.warehouse_id.is_(None)
        )
        warehouse_wide = and_(
            ReplenishmentPolicy.material_id.is_(None), ReplenishmentPolicy.warehouse_id == warehouse_id
        )
        global_wide = and_(
            ReplenishmentPolicy.material_id.is_(None), ReplenishmentPolicy.warehouse_id.is_(None)
        )
        stmt = select(ReplenishmentPolicy).where(
            ReplenishmentPolicy.deleted_at.is_(None),
            ReplenishmentPolicy.is_active.is_(True),
            or_(
                ReplenishmentPolicy.effective_from.is_(None),
                ReplenishmentPolicy.effective_from <= date.today(),
            ),
            or_(pair, material_wide, warehouse_wide, global_wide),
        )
        rows = list(self.db.execute(stmt).scalars().all())
        if not rows:
            return None

        def rank(policy: ReplenishmentPolicy) -> int:
            if policy.material_id == material_id and policy.warehouse_id == warehouse_id:
                return 0
            if policy.material_id == material_id and policy.warehouse_id is None:
                return 1
            if policy.material_id is None and policy.warehouse_id == warehouse_id:
                return 2
            return 3

        rows.sort(key=lambda policy: (rank(policy), policy.id))
        return rows[0]


class ReplenishmentSuggestionRepo:
    def __init__(self, db) -> None:
        self.db = db

    def get_active(self, suggestion_id: int):
        obj = self.db.get(ReplenishmentSuggestion, suggestion_id)
        if obj is None or obj.deleted_at is not None:
            return None
        return obj

    def add(self, obj):
        self.db.add(obj)
        self.db.flush()
        return obj

    def find_open(self, material_id: int, warehouse_id: int):
        stmt = select(ReplenishmentSuggestion).where(
            ReplenishmentSuggestion.material_id == material_id,
            ReplenishmentSuggestion.warehouse_id == warehouse_id,
            ReplenishmentSuggestion.status.in_(_OPEN_STATUSES),
            ReplenishmentSuggestion.deleted_at.is_(None),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list(
        self,
        offset: int,
        limit: int,
        status: str | None = None,
        material_id: int | None = None,
        warehouse_id: int | None = None,
        trigger_type: str | None = None,
    ):
        stmt = select(ReplenishmentSuggestion).where(ReplenishmentSuggestion.deleted_at.is_(None))
        if status:
            stmt = stmt.where(ReplenishmentSuggestion.status == status)
        if material_id is not None:
            stmt = stmt.where(ReplenishmentSuggestion.material_id == material_id)
        if warehouse_id is not None:
            stmt = stmt.where(ReplenishmentSuggestion.warehouse_id == warehouse_id)
        if trigger_type:
            stmt = stmt.where(ReplenishmentSuggestion.trigger_type == trigger_type)
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        rows = (
            self.db.execute(
                stmt.order_by(ReplenishmentSuggestion.generated_at.desc(), ReplenishmentSuggestion.id.desc())
                .offset(offset)
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return list(rows), int(total)

    def next_suggestion_no(self, day: date | None = None) -> str:
        day = day or date.today()
        prefix = "RS-%s-" % day.strftime("%Y%m%d")
        latest = self.db.execute(
            select(func.max(ReplenishmentSuggestion.suggestion_no)).where(
                ReplenishmentSuggestion.suggestion_no.like(prefix + "%")
            )
        ).scalar_one_or_none()
        seq = 1
        if latest:
            tail = latest.rsplit("-", 1)[-1]
            if tail.isdigit():
                seq = int(tail) + 1
        return "%s%04d" % (prefix, seq)
