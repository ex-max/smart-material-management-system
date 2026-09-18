"""库存过账账本：唯一允许修改 inventory / inventory_batch.quantity 的地方。

所有余额变更都必须在同一事务内写一条 inventory_transaction（领域不变量 1）。
入库/出库/调拨/盘点的过账都通过 StockLedger.change() 完成，禁止在别处直接改结存。
"""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.errors import BadRequest
from app.model.base import utcnow
from app.model.inventory import BATCH_DEFAULT_NO, Inventory, InventoryBatch, InventoryTransaction
from app.repository.inventory import InventoryBatchRepo, InventoryRepo, InventoryTransactionRepo
from app.repository.master import MaterialRepo


class StockLedger:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.batches = InventoryBatchRepo(db)
        self.inventories = InventoryRepo(db)
        self.txns = InventoryTransactionRepo(db)

    def change(
        self,
        *,
        key: str,
        material_id: int,
        warehouse_id: int,
        delta: Decimal,
        txn_type: str,
        source_type: str,
        source_id: int | None = None,
        source_no: str | None = None,
        source_line_id: int | None = None,
        operator_id: int | None = None,
        unit_price: Decimal | None = None,
        amount: Decimal | None = None,
        batch_id: int | None = None,
        batch_no: str | None = None,
        production_date: date | None = None,
        expiry_date: date | None = None,
    ) -> InventoryBatch:
        delta = Decimal(delta)
        if delta == 0:
            raise BadRequest("库存变动数量不能为 0")
        batch = self._batch(material_id, warehouse_id, batch_id, batch_no, production_date, expiry_date, operator_id)
        new_batch_qty = batch.quantity + delta
        if new_batch_qty < 0:
            raise BadRequest(
                "可用库存不足：物资 %s 批次 %s 当前 %s，需要 %s"
                % (material_id, batch.batch_no, batch.quantity, -delta)
            )
        batch.quantity = new_batch_qty
        if delta > 0 and batch.inbound_date is None:
            batch.inbound_date = date.today()

        inventory = self._inventory(material_id, warehouse_id, operator_id)
        new_inv_qty = inventory.quantity + delta
        if new_inv_qty < 0:
            raise BadRequest("可用库存不足（汇总）：物资 %s" % material_id)
        inventory.quantity = new_inv_qty
        inventory.version = inventory.version + 1
        inventory.last_txn_at = utcnow()

        self.txns.add(
            InventoryTransaction(
                idem_key=key,
                material_id=material_id,
                warehouse_id=warehouse_id,
                batch_id=batch.id,
                quantity=delta,
                txn_type=txn_type,
                source_type=source_type,
                source_id=source_id,
                source_no=source_no,
                source_line_id=source_line_id,
                balance_after=new_batch_qty,
                unit_price=unit_price,
                amount=amount,
                created_by=operator_id,
            )
        )
        return batch

    def _batch(self, material_id, warehouse_id, batch_id, batch_no, production_date, expiry_date, operator_id):
        if batch_id is not None:
            batch = self.db.get(InventoryBatch, batch_id)
            if batch is None or batch.deleted_at is not None:
                raise BadRequest("批次不存在：" + str(batch_id))
            if batch.material_id != material_id or batch.warehouse_id != warehouse_id:
                raise BadRequest("批次不属于该物资/仓库：" + str(batch_id))
            return batch
        if batch_no is None:
            batch_no = BATCH_DEFAULT_NO
        batch = self.batches.get_grain(material_id, warehouse_id, batch_no, for_update=True)
        if batch is None:
            MaterialRepo(self.db).get(material_id)
            batch = InventoryBatch(
                material_id=material_id,
                warehouse_id=warehouse_id,
                batch_no=batch_no,
                is_default=batch_no == BATCH_DEFAULT_NO,
                production_date=production_date,
                expiry_date=expiry_date,
                inbound_date=date.today(),
                quantity=Decimal("0"),
                status="NORMAL",
                created_by=operator_id,
            )
            self.batches.add(batch)
        else:
            if production_date is not None and batch.production_date is None:
                batch.production_date = production_date
            if expiry_date is not None and batch.expiry_date is None:
                batch.expiry_date = expiry_date
        return batch

    def _inventory(self, material_id, warehouse_id, operator_id):
        inventory = self.inventories.get_grain(material_id, warehouse_id, for_update=True)
        if inventory is None:
            inventory = Inventory(
                material_id=material_id,
                warehouse_id=warehouse_id,
                quantity=Decimal("0"),
                locked_qty=Decimal("0"),
                version=0,
                created_by=operator_id,
            )
            self.inventories.add(inventory)
        return inventory
