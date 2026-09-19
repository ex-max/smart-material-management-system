"""演示数据种子：通过 HTTP API 生成一套符合业务状态机与库存不变量的现实数据。

为什么走 API 而不是直接写库：单据状态机、库存流水与结存必须由 service 层保证
（AGENTS 第五节：库存余额只能由流水推导、单据必须走状态机）。

用法::

    # 本地开发（后端跑在 8000）
    cd backend && ERP_BASE_URL=http://127.0.0.1:8000 .venv/bin/python -m scripts.seed_demo
    # 一键部署（web 容器反代在 8080）
    cd backend && ERP_BASE_URL=http://127.0.0.1:8080 .venv/bin/python -m scripts.seed_demo

幂等：主数据按编码「存在即跳过」；演示单据以 [DEMO] 标记，检测到已存在则整段跳过。
依赖：仅 Python 标准库。
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta
from decimal import Decimal

BASE = os.environ.get("ERP_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ADMIN_USER = os.environ.get("ERP_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ERP_ADMIN_PASSWORD", "admin123")
DEMO = "[DEMO]"
TODAY = date.today()


def d(days: int) -> str:
    return str(TODAY + timedelta(days=days))


class ApiError(RuntimeError):
    pass


def _call(method: str, path: str, token: str | None = None, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            msg = json.loads(raw).get("message", raw)
        except json.JSONDecodeError:
            msg = raw
        raise ApiError("%s %s -> HTTP %s: %s" % (method, path, exc.code, msg)) from None
    if payload.get("code") != 0:
        raise ApiError("%s %s -> code=%s: %s" % (method, path, payload.get("code"), payload.get("message")))
    return payload.get("data")


def post(token, path, body=None):
    return _call("POST", path, token, body)


def get(token, path):
    return _call("GET", path, token)


def list_items(token, path):
    return get(token, path + "?page=1&page_size=200")["items"]


def by_code(items):
    return {item["code"]: item for item in items}


# ---------------------------------------------------------------------------
# 主数据
# ---------------------------------------------------------------------------
UNITS = [
    ("PCS", "个", 0),
    ("BOX", "箱", 0),
    ("BAG", "包", 0),
    ("PAIR", "双", 0),
    ("SET", "套", 0),
    ("ROLL", "卷", 0),
    ("BOTTLE", "瓶", 0),
    ("UNIT", "台", 0),
    ("KG", "千克", 2),
    ("M", "米", 2),
]

# (code, name, parent_code)
CATEGORIES = [
    ("OFFICE", "办公用品", None),
    ("OFFICE-PAPER", "纸张文具", "OFFICE"),
    ("OFFICE-DEVICE", "办公设备耗材", "OFFICE"),
    ("HARDWARE", "五金机电", None),
    ("HARDWARE-FASTENER", "紧固件", "HARDWARE"),
    ("HARDWARE-TOOL", "工具仪表", "HARDWARE"),
    ("PPE", "劳保用品", None),
    ("PPE-PROTECT", "防护用品", "PPE"),
    ("PPE-CLOTHES", "劳保服装", "PPE"),
    ("ELEC", "电子电气", None),
    ("ELEC-CABLE", "电线电缆", "ELEC"),
    ("ELEC-SENSOR", "传感器与元件", "ELEC"),
    ("PACK", "包装材料", None),
    ("PACK-BOX", "纸箱与膜", "PACK"),
    ("PACK-LABEL", "标签耗材", "PACK"),
    ("CLEAN", "清洁用品", None),
    ("CLEAN-AGENT", "清洁剂", "CLEAN"),
    ("CLEAN-TOOL", "清洁工具", "CLEAN"),
    ("RAW", "原材料", None),
    ("RAW-STEEL", "金属材料", "RAW"),
    ("RAW-PLASTIC", "塑料原料", "RAW"),
]

SUPPLIERS = [
    ("SUP-001", "上海晨光文具有限公司", "晨光文具", "王丽", "021-61234567", "sales@mg-paper.cn", "上海市奉贤区工业路 128 号", "月结30天", 5, 4.6),
    ("SUP-002", "苏州工业园区五金机电有限公司", "苏州五金", "李强", "0512-67891234", "lq@szhardware.com", "苏州市工业园区娄葑镇东环路 66 号", "月结30天", 7, 4.3),
    ("SUP-003", "无锡安全防护用品有限公司", "无锡安防", "张敏", "0510-82345678", "zhangm@wx-safety.com", "无锡市新吴区锡兴路 8 号", "月结45天", 10, 4.5),
    ("SUP-004", "昆山华芯电子科技有限公司", "华芯电子", "陈涛", "0512-55667788", "chent@kshuaxin.com", "昆山市开发区前进东路 289 号", "月结45天", 12, 4.1),
    ("SUP-005", "杭州佳包包装材料有限公司", "佳包包装", "周洁", "0571-88990011", "zhouj@hzjiabao.com", "杭州市余杭区仓前街道文一西路 1500 号", "月结30天", 6, 4.0),
    ("SUP-006", "南京净美清洁用品有限公司", "南京净美", "赵磊", "025-83334455", "zhaol@njjm-clean.com", "南京市江宁区秣周东路 12 号", "月结30天", 8, 4.4),
    ("SUP-007", "宝钢金属材料贸易有限公司", "宝钢贸易", "孙浩", "021-58886666", "sunhao@bgmetal.com", "上海市宝山区同济路 1888 号", "款到发货", 15, 4.7),
    ("SUP-008", "浙江华塑原料有限公司", "华塑原料", "吴昊", "0574-87223344", "wuhao@zjhuasu.com", "宁波市镇海区大运路 9 号", "款到发货", 14, 4.2),
]

WAREHOUSES = [
    ("WH01", "上海总部仓", "上海市浦东新区张江高科技园区祖冲之路 899 号"),
    ("WH02", "苏州生产辅料仓", "苏州市工业园区星湖街 328 号"),
    ("WH03", "备品备件仓", "上海市嘉定区安亭镇园大路 12 号"),
]

# (warehouse_code, code, name, zone)
LOCATIONS = [
    ("WH01", "WH01-A-01-01", "货架A1-01", "A区"),
    ("WH01", "WH01-A-01-02", "货架A1-02", "A区"),
    ("WH01", "WH01-B-02-01", "货架B2-01", "B区"),
    ("WH01", "WH01-C-03-01", "待检区", "C区"),
    ("WH02", "WH02-P-01-01", "生产辅料区01", "P区"),
    ("WH02", "WH02-P-01-02", "生产辅料区02", "P区"),
    ("WH02", "WH02-Q-02-01", "危化品暂存区", "Q区"),
    ("WH03", "WH03-S-01-01", "备件区01", "S区"),
    ("WH03", "WH03-S-01-02", "备件区02", "S区"),
    ("WH03", "WH03-S-01-03", "备件区03", "S区"),
]

# (code, name, spec, category, unit, brand, safety, max_stock, rop, lead_time, batch, shelf_life, supplier, abc, price)
MATERIALS = [
    ("M-PAPER-001", "A4复印纸 70g 500张/包", "70g 210x297mm", "OFFICE-PAPER", "BOX", "晨光", 20, 200, 40, 5, False, None, "SUP-001", "A", 120),
    ("M-PEN-001", "中性笔 0.5mm 黑色", "0.5mm 黑色", "OFFICE-PAPER", "PCS", "晨光", 200, 2000, 500, 5, False, None, "SUP-001", "B", 1.5),
    ("M-FOLDER-001", "档案盒 A4 55mm", "A4 55mm 牛皮纸", "OFFICE-PAPER", "PCS", "得力", 50, 500, 100, 6, False, None, "SUP-001", "C", 6),
    ("M-NOTE-001", "便利贴 76x76mm", "76x76mm 100张", "OFFICE-PAPER", "BAG", "3M", 30, 300, 60, 7, False, None, "SUP-001", "C", 8),
    ("M-PRINT-001", "硒鼓 CF218A", "HP LaserJet Pro M132", "OFFICE-DEVICE", "PCS", "惠普", 5, 30, 10, 10, False, None, "SUP-001", "A", 320),
    ("M-FAST-001", "内六角螺栓 M8x30", "M8x30 304不锈钢", "HARDWARE-FASTENER", "PCS", "晋亿", 500, 5000, 1000, 7, False, None, "SUP-002", "B", 0.5),
    ("M-FAST-002", "不锈钢螺母 M8", "M8 304不锈钢", "HARDWARE-FASTENER", "PCS", "晋亿", 800, 8000, 1500, 7, False, None, "SUP-002", "B", 0.2),
    ("M-FAST-003", "平垫圈 M8", "M8 镀锌", "HARDWARE-FASTENER", "BAG", "标准件", 40, 400, 80, 7, False, None, "SUP-002", "C", 15),
    ("M-TOOL-001", "棘轮扳手 12件套", "12件套 铬钒钢", "HARDWARE-TOOL", "SET", "世达", 5, 30, 8, 12, False, None, "SUP-002", "A", 85),
    ("M-TOOL-002", "数字万用表 UT61E", "UT61E 真有效值", "HARDWARE-TOOL", "UNIT", "优利德", 3, 20, 6, 15, False, None, "SUP-004", "A", 280),
    ("M-PPE-001", "丁腈手套 M码", "M码 12双/打", "PPE-PROTECT", "PAIR", "3M", 200, 2000, 400, 10, False, None, "SUP-003", "B", 1.2),
    ("M-PPE-002", "防砸安全鞋 43码", "43码 钢包头", "PPE-CLOTHES", "PAIR", "霍尼韦尔", 20, 200, 40, 12, False, None, "SUP-003", "A", 95),
    ("M-PPE-003", "KN95口罩", "KN95 50只/盒", "PPE-PROTECT", "BOX", "3M", 50, 500, 100, 8, False, None, "SUP-003", "B", 45),
    ("M-ELEC-001", "RVV电源线 3x1.5mm²", "3x1.5mm² 100m/卷", "ELEC-CABLE", "M", "珠江", 200, 2000, 400, 10, False, None, "SUP-004", "B", 6.5),
    ("M-ELEC-002", "光电传感器 E3Z-D61", "E3Z-D61 NPN", "ELEC-SENSOR", "PCS", "欧姆龙", 10, 100, 20, 14, False, None, "SUP-004", "A", 180),
    ("M-ELEC-003", "中间继电器 JZX-22F", "JZX-22F 24VDC", "ELEC-SENSOR", "PCS", "正泰", 20, 200, 40, 12, False, None, "SUP-004", "B", 22),
    ("M-PACK-001", "五层瓦楞纸箱 60x40x40", "60x40x40cm", "PACK-BOX", "BOX", "佳包", 100, 1000, 200, 6, False, None, "SUP-005", "B", 7.5),
    ("M-PACK-002", "自粘标签 100x80mm", "100x80mm 500枚/卷", "PACK-LABEL", "ROLL", "得力", 20, 200, 40, 6, False, None, "SUP-005", "C", 25),
    ("M-PACK-003", "缠绕膜 50cm", "50cm 宽 3kg/卷", "PACK-BOX", "ROLL", "佳包", 30, 300, 60, 6, False, None, "SUP-005", "C", 32),
    ("M-CLEAN-001", "84消毒液 500ml", "500ml/瓶", "CLEAN-AGENT", "BOTTLE", "净美", 60, 600, 120, 8, True, 730, "SUP-006", "B", 12),
    ("M-CLEAN-002", "工业清洗剂 5L", "5L/桶 中性", "CLEAN-AGENT", "BOTTLE", "净美", 20, 200, 40, 8, True, 1080, "SUP-006", "B", 55),
    ("M-CLEAN-003", "无尘擦拭布 30x30cm", "30x30cm 100片/包", "CLEAN-TOOL", "BAG", "净美", 40, 400, 80, 8, False, None, "SUP-006", "C", 18),
    ("M-CLEAN-004", "免洗洗手液 500ml", "500ml/瓶", "CLEAN-AGENT", "BOTTLE", "净美", 30, 300, 60, 8, True, 730, "SUP-006", "C", 16),
    ("M-RAW-001", "冷轧钢板 1.5mm", "1.5x1250xC", "RAW-STEEL", "KG", "宝钢", 1000, 10000, 2000, 15, False, None, "SUP-007", "A", 4.8),
    ("M-RAW-002", "ABS塑料粒子 757K", "757K 本色", "RAW-PLASTIC", "KG", "华塑", 500, 5000, 1000, 14, True, None, "SUP-008", "A", 12.5),
    ("M-RAW-003", "铝合金型材 6063", "6063-T5 40x40", "RAW-STEEL", "M", "南山", 100, 1000, 200, 15, False, None, "SUP-007", "B", 28),
]

PRICE = {row[0]: Decimal(str(row[14])) for row in MATERIALS}


def seed_master(token):
    units = by_code(list_items(token, "/api/v1/units"))
    for code, name, scale in UNITS:
        if code not in units:
            units[code] = post(token, "/api/v1/units", {"code": code, "name": name, "scale": scale, "is_active": True})

    categories = by_code(list_items(token, "/api/v1/material-categories"))
    for sort_no, (code, name, parent) in enumerate(CATEGORIES, start=1):
        if code not in categories:
            body = {"code": code, "name": name, "sort_no": sort_no, "is_active": True}
            if parent:
                body["parent_id"] = categories[parent]["id"]
            categories[code] = post(token, "/api/v1/material-categories", body)

    suppliers = by_code(list_items(token, "/api/v1/suppliers"))
    for code, name, short, contact, phone, email, address, terms, lead, rating in SUPPLIERS:
        if code not in suppliers:
            suppliers[code] = post(
                token,
                "/api/v1/suppliers",
                {
                    "code": code,
                    "name": name,
                    "short_name": short,
                    "contact_person": contact,
                    "contact_phone": phone,
                    "email": email,
                    "address": address,
                    "payment_terms": terms,
                    "lead_time_days": lead,
                    "rating": rating,
                    "status": "ACTIVE",
                },
            )

    warehouses = by_code(list_items(token, "/api/v1/warehouses"))
    for code, name, address in WAREHOUSES:
        if code not in warehouses:
            warehouses[code] = post(
                token, "/api/v1/warehouses", {"code": code, "name": name, "address": address, "is_active": True}
            )

    locations = by_code(list_items(token, "/api/v1/locations"))
    for warehouse_code, code, name, zone in LOCATIONS:
        if code not in locations:
            locations[code] = post(
                token,
                "/api/v1/locations",
                {"warehouse_id": warehouses[warehouse_code]["id"], "code": code, "name": name, "zone": zone},
            )

    materials = by_code(list_items(token, "/api/v1/materials"))
    for row in MATERIALS:
        if row[0] in materials:
            continue
        (code, name, spec, cat, unit, brand, safety, max_stock, rop, lead, batch, shelf, supplier, abc, _price) = row
        materials[code] = post(
            token,
            "/api/v1/materials",
            {
                "code": code,
                "name": name,
                "spec": spec,
                "category_id": categories[cat]["id"],
                "unit_id": units[unit]["id"],
                "brand": brand,
                "safety_stock": safety,
                "max_stock": max_stock,
                "reorder_point": rop,
                "lead_time_days": lead,
                "is_batch_managed": batch,
                "shelf_life_days": shelf,
                "default_supplier_id": suppliers[supplier]["id"],
                "abc_class": abc,
                "status": "ACTIVE",
            },
        )
    print(
        "主数据：单位 %d / 分类 %d / 供应商 %d / 仓库 %d / 库位 %d / 物资 %d"
        % (len(units), len(categories), len(suppliers), len(warehouses), len(locations), len(materials))
    )
    return materials, warehouses, suppliers


# ---------------------------------------------------------------------------
# 单据
# ---------------------------------------------------------------------------
def demo_documents_exist(token) -> bool:
    for path in (
        "/api/v1/purchase-requisitions",
        "/api/v1/purchase-orders",
        "/api/v1/supplier-deliveries",
        "/api/v1/outbound-orders",
        "/api/v1/transfer-orders",
        "/api/v1/stocktake-orders",
    ):
        for item in list_items(token, path):
            if DEMO in (item.get("title") or "") or DEMO in (item.get("remark") or ""):
                return True
    return False


def create_pr(token, title, dept, priority, reason, lines):
    return post(
        token,
        "/api/v1/purchase-requisitions",
        {
            "title": DEMO + " " + title,
            "dept_name": dept,
            "priority": priority,
            "expected_date": d(12),
            "reason": reason,
            "remark": DEMO,
            "items": lines,
        },
    )


def convert_to_po(token, pr, supplier, expected_days=15):
    items = [
        {"pr_item_id": item["id"], "unit_price": float(PRICE_FOR_ID[item["material_id"]]), "tax_rate": 13}
        for item in pr["items"]
    ]
    return post(
        token,
        "/api/v1/purchase-requisitions/%d/convert-to-po" % pr["id"],
        {
            "supplier_id": supplier["id"],
            "currency": "CNY",
            "payment_terms": "月结30天",
            "expected_date": d(expected_days),
            "items": items,
        },
    )


def create_delivery(token, po, lines):
    po_items = {item["material_id"]: item for item in po["items"]}
    body_items = []
    for line in lines:
        po_item = po_items[line["material_id"]]
        entry = {"po_item_id": po_item["id"], "quantity": line["quantity"]}
        for key in ("batch_no", "production_date", "expiry_date", "inspection_result", "remark"):
            if line.get(key) is not None:
                entry[key] = line[key]
        body_items.append(entry)
    return post(
        token,
        "/api/v1/supplier-deliveries",
        {"po_id": po["id"], "delivery_date": str(TODAY), "received_by": None, "remark": DEMO, "items": body_items},
    )


def accept_delivery(token, delivery, warehouse, rejected=None):
    rejected = rejected or {}
    items = []
    for item in delivery["items"]:
        rej = Decimal(str(rejected.get(item["id"], 0)))
        qty = Decimal(str(item["quantity"]))
        items.append(
            {
                "delivery_item_id": item["id"],
                "accepted_qty": float(qty - rej),
                "rejected_qty": float(rej),
                "inspection_result": "PASS" if rej == 0 else "CONCESSION",
                "remark": None,
            }
        )
    return post(
        token,
        "/api/v1/supplier-deliveries/%d/accept" % delivery["id"],
        {"warehouse_id": warehouse["id"], "location_id": None, "remark": DEMO, "items": items},
    )


def received(token, po, warehouse, rejected=None):
    delivery = create_delivery(token, po, [{"material_id": i["material_id"], "quantity": float(i["quantity"])} for i in po["items"]])
    delivery = post(token, "/api/v1/supplier-deliveries/%d/submit" % delivery["id"])
    inbound = accept_delivery(token, delivery, warehouse, rejected)
    inbound = post(token, "/api/v1/inbound-orders/%d/post" % inbound["id"])
    return post(token, "/api/v1/inbound-orders/%d/complete" % inbound["id"])


def seed_documents(token, materials, warehouses, suppliers):
    home = warehouses["WH01"]
    prod = warehouses["WH02"]
    spare = warehouses["WH03"]

    # A. 请购 -> 审批 -> 转采购订单 -> 确认 -> 到货 -> 验收入库 -> 完成（办公用品，全收）
    pr_a = create_pr(
        token,
        "办公用品季度补充申请",
        "行政部",
        3,
        "A4纸、笔类低于安全库存，需补充",
        [
            {"material_id": materials["M-PAPER-001"]["id"], "quantity": 50, "purpose": "日常打印"},
            {"material_id": materials["M-PEN-001"]["id"], "quantity": 500, "purpose": "日常办公"},
            {"material_id": materials["M-FOLDER-001"]["id"], "quantity": 200, "purpose": "档案归档"},
        ],
    )
    pr_a = post(token, "/api/v1/purchase-requisitions/%d/submit" % pr_a["id"])
    pr_a = post(token, "/api/v1/purchase-requisitions/%d/approve" % pr_a["id"])
    po_a = convert_to_po(token, pr_a, suppliers["SUP-001"])  # 转单即已审（状态机 APPROVED）
    received(token, po_a, home)

    # B. 五金紧固件：部分到货（含 1 行让步接收），入库单停留在执行中
    pr_b = create_pr(
        token,
        "五金紧固件补充申请",
        "生产部",
        2,
        "生产线装配需求增加，紧固件库存不足",
        [
            {"material_id": materials["M-FAST-001"]["id"], "quantity": 2000, "purpose": "装配"},
            {"material_id": materials["M-FAST-002"]["id"], "quantity": 3000, "purpose": "装配"},
            {"material_id": materials["M-TOOL-001"]["id"], "quantity": 30, "purpose": "工装配套"},
        ],
    )
    pr_b = post(token, "/api/v1/purchase-requisitions/%d/submit" % pr_b["id"])
    pr_b = post(token, "/api/v1/purchase-requisitions/%d/approve" % pr_b["id"])
    po_b = convert_to_po(token, pr_b, suppliers["SUP-002"])
    delivery_b = create_delivery(
        token,
        po_b,
        [
            {"material_id": materials["M-FAST-001"]["id"], "quantity": 2000},
            {"material_id": materials["M-FAST-002"]["id"], "quantity": 3000},
            {"material_id": materials["M-TOOL-001"]["id"], "quantity": 30},
        ],
    )
    delivery_b = post(token, "/api/v1/supplier-deliveries/%d/submit" % delivery_b["id"])
    reject_b = {item["id"]: 50 for item in delivery_b["items"] if item["material_id"] == materials["M-FAST-002"]["id"]}
    inbound_b = accept_delivery(token, delivery_b, home, reject_b)
    post(token, "/api/v1/inbound-orders/%d/post" % inbound_b["id"])  # 不 complete，保留执行中

    # C. 劳保用品：已确认采购订单 + 一张草稿到货单 + 一张待验收到货单
    pr_c = create_pr(
        token,
        "劳保用品补充申请",
        "安全环保部",
        2,
        "新员工入职及年度劳保更换",
        [
            {"material_id": materials["M-PPE-001"]["id"], "quantity": 1000, "purpose": "车间防护"},
            {"material_id": materials["M-PPE-002"]["id"], "quantity": 60, "purpose": "新员工发放"},
        ],
    )
    pr_c = post(token, "/api/v1/purchase-requisitions/%d/submit" % pr_c["id"])
    pr_c = post(token, "/api/v1/purchase-requisitions/%d/approve" % pr_c["id"])
    po_c = convert_to_po(token, pr_c, suppliers["SUP-003"])
    create_delivery(
        token,
        po_c,
        [
            {"material_id": materials["M-PPE-001"]["id"], "quantity": 600},
            {"material_id": materials["M-PPE-002"]["id"], "quantity": 60},
        ],
    )
    delivery_c2 = create_delivery(token, po_c, [{"material_id": materials["M-PPE-001"]["id"], "quantity": 400}])
    post(token, "/api/v1/supplier-deliveries/%d/submit" % delivery_c2["id"])

    # D. 批次物资（清洁剂）：到货带批次与效期，验收入苏州辅料仓并完成
    pr_d = create_pr(
        token,
        "清洁剂批次采购申请",
        "后勤部",
        3,
        "厂区清洁消耗，需批次与效期管理",
        [
            {"material_id": materials["M-CLEAN-001"]["id"], "quantity": 300, "purpose": "厂区消毒"},
            {"material_id": materials["M-CLEAN-002"]["id"], "quantity": 120, "purpose": "设备清洗"},
        ],
    )
    pr_d = post(token, "/api/v1/purchase-requisitions/%d/submit" % pr_d["id"])
    pr_d = post(token, "/api/v1/purchase-requisitions/%d/approve" % pr_d["id"])
    po_d = convert_to_po(token, pr_d, suppliers["SUP-006"], expected_days=10)
    delivery_d = create_delivery(
        token,
        po_d,
        [
            {
                "material_id": materials["M-CLEAN-001"]["id"],
                "quantity": 300,
                "batch_no": "XL" + str(TODAY - timedelta(days=45)).replace("-", ""),
                "production_date": d(-45),
                "expiry_date": d(685),
                "inspection_result": "PASS",
            },
            {
                "material_id": materials["M-CLEAN-002"]["id"],
                "quantity": 120,
                "batch_no": "QX" + str(TODAY - timedelta(days=30)).replace("-", ""),
                "production_date": d(-30),
                "expiry_date": d(1050),
                "inspection_result": "PASS",
            },
        ],
    )
    delivery_d = post(token, "/api/v1/supplier-deliveries/%d/submit" % delivery_d["id"])
    inbound_d = accept_delivery(token, delivery_d, prod)
    inbound_d = post(token, "/api/v1/inbound-orders/%d/post" % inbound_d["id"])
    post(token, "/api/v1/inbound-orders/%d/complete" % inbound_d["id"])

    # E. 仅审批未转单 / 待审 / 草稿 的请购单
    pr_e = create_pr(
        token,
        "电子元件备件申请",
        "设备部",
        4,
        "产线备件安全库存偏低",
        [
            {"material_id": materials["M-ELEC-002"]["id"], "quantity": 20, "purpose": "设备备件"},
            {"material_id": materials["M-ELEC-003"]["id"], "quantity": 50, "purpose": "控制柜备件"},
            {"material_id": materials["M-ELEC-001"]["id"], "quantity": 500, "purpose": "检修备料"},
        ],
    )
    pr_e = post(token, "/api/v1/purchase-requisitions/%d/submit" % pr_e["id"])
    post(token, "/api/v1/purchase-requisitions/%d/approve" % pr_e["id"])  # 留在 APPROVED

    pr_f = create_pr(
        token,
        "冷轧钢板采购申请",
        "生产部",
        3,
        "下季度生产计划备料",
        [{"material_id": materials["M-RAW-001"]["id"], "quantity": 3000, "purpose": "钣金生产"}],
    )
    post(token, "/api/v1/purchase-requisitions/%d/submit" % pr_f["id"])  # 留在 PENDING

    create_pr(
        token,
        "清洁耗材补充申请",
        "后勤部",
        4,
        "擦拭布库存接近再订货点",
        [{"material_id": materials["M-CLEAN-003"]["id"], "quantity": 100, "purpose": "厂区清洁"}],
    )  # 留在 DRAFT

    # F. 一张草稿采购订单
    post(
        token,
        "/api/v1/purchase-orders",
        {
            "supplier_id": suppliers["SUP-005"]["id"],
            "order_date": str(TODAY),
            "expected_date": d(10),
            "currency": "CNY",
            "payment_terms": "月结30天",
            "remark": DEMO + " 包装材料年度框架订单",
            "items": [
                {"material_id": materials["M-PACK-001"]["id"], "quantity": 500, "unit_price": 7.5, "tax_rate": 13},
                {"material_id": materials["M-PACK-002"]["id"], "quantity": 40, "unit_price": 25, "tax_rate": 13},
            ],
        },
    )

    # G. 出库：正常领料（完成）、报废（完成）、草稿
    out1 = post(
        token,
        "/api/v1/outbound-orders",
        {
            "warehouse_id": home["id"],
            "source_type": "REQUISITION_ISSUE",
            "dept_name": "生产部",
            "remark": DEMO + " 生产车间领料",
            "items": [
                {"material_id": materials["M-PAPER-001"]["id"], "quantity": 5, "unit_price": 120},
                {"material_id": materials["M-PEN-001"]["id"], "quantity": 50, "unit_price": 1.5},
            ],
        },
    )
    out1 = post(token, "/api/v1/outbound-orders/%d/post" % out1["id"])
    post(token, "/api/v1/outbound-orders/%d/complete" % out1["id"])

    out2 = post(
        token,
        "/api/v1/outbound-orders",
        {
            "warehouse_id": home["id"],
            "source_type": "SCRAP",
            "dept_name": "行政部",
            "remark": DEMO + " 破损档案盒报废",
            "items": [{"material_id": materials["M-FOLDER-001"]["id"], "quantity": 5, "unit_price": 6}],
        },
    )
    out2 = post(token, "/api/v1/outbound-orders/%d/post" % out2["id"])
    post(token, "/api/v1/outbound-orders/%d/complete" % out2["id"])

    post(
        token,
        "/api/v1/outbound-orders",
        {
            "warehouse_id": home["id"],
            "source_type": "REQUISITION_ISSUE",
            "dept_name": "行政部",
            "remark": DEMO + " 办公用品领用（待过账）",
            "items": [{"material_id": materials["M-FOLDER-001"]["id"], "quantity": 20, "unit_price": 6}],
        },
    )

    # H. 调拨：完成 + 草稿
    tr1 = post(
        token,
        "/api/v1/transfer-orders",
        {
            "from_warehouse_id": home["id"],
            "to_warehouse_id": spare["id"],
            "transfer_date": str(TODAY),
            "remark": DEMO + " 备件调拨至备件仓",
            "items": [
                {"material_id": materials["M-TOOL-001"]["id"], "quantity": 5},
                {"material_id": materials["M-FAST-001"]["id"], "quantity": 200},
            ],
        },
    )
    tr1 = post(token, "/api/v1/transfer-orders/%d/post" % tr1["id"])
    post(token, "/api/v1/transfer-orders/%d/complete" % tr1["id"])

    post(
        token,
        "/api/v1/transfer-orders",
        {
            "from_warehouse_id": home["id"],
            "to_warehouse_id": prod["id"],
            "transfer_date": str(TODAY),
            "remark": DEMO + " 紧固件调拨（待过账）",
            "items": [{"material_id": materials["M-FAST-002"]["id"], "quantity": 300}],
        },
    )

    # I. 盘点：上海仓抽盘并完成（含盘亏/盘盈），苏州仓草稿
    st1 = post(
        token,
        "/api/v1/stocktake-orders",
        {
            "warehouse_id": home["id"],
            "scope": "PARTIAL",
            "planned_date": str(TODAY),
            "remark": DEMO + " 上海仓月度抽盘",
            "items": [
                {"material_id": materials["M-PAPER-001"]["id"]},
                {"material_id": materials["M-PEN-001"]["id"]},
                {"material_id": materials["M-FAST-001"]["id"]},
            ],
        },
    )
    st1 = post(token, "/api/v1/stocktake-orders/%d/start" % st1["id"])
    detail = get(token, "/api/v1/stocktake-orders/%d" % st1["id"])
    counts = []
    for item in detail["items"]:
        book = Decimal(str(item["book_qty"]))
        actual = book
        reason = "账实相符"
        if item["material_id"] == materials["M-PAPER-001"]["id"]:
            actual = book - Decimal("2")
            reason = "搬运破损 2 箱"
        elif item["material_id"] == materials["M-FAST-001"]["id"]:
            actual = book + Decimal("10")
            reason = "上期漏记退料 10 个"
        counts.append({"stocktake_item_id": item["id"], "actual_qty": float(actual), "reason": reason})
    post(token, "/api/v1/stocktake-orders/%d/counts" % st1["id"], {"items": counts})
    post(token, "/api/v1/stocktake-orders/%d/complete" % st1["id"])

    post(
        token,
        "/api/v1/stocktake-orders",
        {
            "warehouse_id": prod["id"],
            "scope": "PARTIAL",
            "planned_date": d(3),
            "remark": DEMO + " 苏州辅料仓计划抽盘",
            "items": [{"material_id": materials["M-CLEAN-001"]["id"]}],
        },
    )

    # J. 预警扫描
    scan = post(token, "/api/v1/stock-alerts/scan")
    print("预警扫描：scanned=%s created=%s" % (scan.get("scanned"), scan.get("created")))


def summarize(token):
    rows = [
        ("请购单", "/api/v1/purchase-requisitions"),
        ("采购订单", "/api/v1/purchase-orders"),
        ("到货/验收单", "/api/v1/supplier-deliveries"),
        ("入库单", "/api/v1/inbound-orders"),
        ("出库单", "/api/v1/outbound-orders"),
        ("调拨单", "/api/v1/transfer-orders"),
        ("盘点单", "/api/v1/stocktake-orders"),
        ("库存预警", "/api/v1/stock-alerts"),
        ("库存结存", "/api/v1/inventory"),
        ("库存流水", "/api/v1/inventory/transactions"),
    ]
    print("—— 数据统计 ——")
    for label, path in rows:
        data = get(token, path + "?page=1&page_size=1")
        print("  %-12s %s" % (label, data["total"]))
    reconcile = get(token, "/api/v1/inventory/reconcile")
    print("  对账结果     ok=%s（批次/流水/负结存四项差异应为空）" % reconcile["ok"])


# 全局：material_id -> 单价（convert 时使用）
PRICE_FOR_ID: dict[int, Decimal] = {}


def main() -> int:
    print("目标：%s （管理员 %s）" % (BASE, ADMIN_USER))
    token = post(None, "/api/v1/auth/login", {"username": ADMIN_USER, "password": ADMIN_PASSWORD})["access_token"]
    materials, warehouses, suppliers = seed_master(token)
    PRICE_FOR_ID.update({materials[code]["id"]: PRICE[code] for code in PRICE})
    if demo_documents_exist(token):
        print("检测到 [DEMO] 单据已存在，跳过单据生成（幂等）。")
    else:
        seed_documents(token, materials, warehouses, suppliers)
        print("单据生成完成。")
    summarize(token)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ApiError as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)
