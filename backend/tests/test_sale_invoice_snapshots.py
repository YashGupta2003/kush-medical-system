"""Issue 5: sale invoice + snapshot persistence and snapshot-based outputs."""
from decimal import Decimal

from app import models
from app.services import stock_service, pos_service, sales_lookup_service, profit_analytics_service


def _med(db_session, tenant, name="SNAP MED", mrp=100.00, net_rate=60.00, stock=50):
    m = models.Medicine(
        tenant_id=tenant.id, particulars=name, normalized_name=name.upper(),
        mrp=Decimal(str(mrp)), net_rate=Decimal(str(net_rate)),
        current_stock=Decimal(str(stock)),
    )
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)
    return m


def test_record_sale_persists_invoice_and_snapshots(db_session, tenant, owner_user):
    med = _med(db_session, tenant, mrp=125.50, net_rate=80.25, stock=20)

    result = stock_service.record_sale(
        db_session, tenant.id, med.id, qty_sold=2, created_by_user_id=owner_user.id, commit=True
    )

    assert result["sale_id"] is not None
    assert result["sale_invoice_id"] is not None
    assert result["sale_invoice_number"]
    assert result["qty_sold"] == 2.0
    assert result["unit_mrp_snapshot"] == 125.50
    assert result["unit_cost_snapshot"] == 80.25
    assert result["line_total"] == 251.00
    assert result["line_profit"] == 90.50

    sale = db_session.get(models.Sale, result["sale_id"])
    assert sale.sale_invoice_id == result["sale_invoice_id"]
    assert float(sale.unit_mrp_snapshot) == 125.50
    assert float(sale.unit_cost_snapshot) == 80.25
    assert float(sale.line_total) == 251.00
    assert float(sale.line_profit) == 90.50

    inv = db_session.get(models.SaleInvoice, sale.sale_invoice_id)
    assert inv.invoice_number == result["sale_invoice_number"]
    assert float(inv.total_amount) == 251.00
    assert float(inv.total_profit) == 90.50


def test_cart_sale_creates_one_invoice_for_multiple_lines_with_snapshot_totals(db_session, tenant, owner_user):
    a = _med(db_session, tenant, name="CART A", mrp=100.00, net_rate=70.00, stock=20)
    b = _med(db_session, tenant, name="CART B", mrp=50.00, net_rate=30.00, stock=20)

    result = pos_service.record_cart_sale(
        db_session, tenant.id,
        items=[{"medicine_id": a.id, "qty_sold": 1}, {"medicine_id": b.id, "qty_sold": 2}],
        created_by_user_id=owner_user.id,
    )

    assert result["status"] == "recorded"
    assert result["sale_invoice_id"] is not None
    assert result["sale_invoice_number"]
    assert result["total_value"] == 200.00
    assert result["subtotal_amount"] == 200.00
    assert result["tax_amount"] == 0.00
    assert result["total_profit"] == 70.00
    assert len(result["results"]) == 2

    invoice_ids = {r["sale_invoice_id"] for r in result["results"]}
    assert invoice_ids == {result["sale_invoice_id"]}
    assert {r["sale_invoice_number"] for r in result["results"]} == {result["sale_invoice_number"]}

    inv = db_session.get(models.SaleInvoice, result["sale_invoice_id"])
    assert inv is not None
    sales = db_session.query(models.Sale).filter(models.Sale.sale_invoice_id == inv.id).all()
    assert len(sales) == 2
    assert float(inv.total_amount) == 200.00
    assert float(inv.total_profit) == 70.00


def test_profit_margin_uses_sale_snapshots_not_current_medicine_prices(db_session, tenant, owner_user):
    med = _med(db_session, tenant, name="MARGIN SNAP", mrp=100.00, net_rate=50.00, stock=10)
    stock_service.record_sale(db_session, tenant.id, med.id, qty_sold=1, created_by_user_id=owner_user.id, commit=True)

    # Change current prices after sale; realized metrics must remain based on snapshot
    med.mrp = Decimal("200.00")
    med.net_rate = Decimal("180.00")
    db_session.commit()

    result = profit_analytics_service.get_profit_margin_analysis(db_session, tenant.id)
    assert result["realized_shop_average_margin_pct"] == 50.0
    assert result["source"] == "sale_snapshots"


def test_recent_sales_prefers_snapshot_names_and_includes_snapshot_fields(db_session, tenant, owner_user):
    med = _med(db_session, tenant, name="OLD NAME", mrp=30.00, net_rate=20.00, stock=10)
    stock_service.record_sale(db_session, tenant.id, med.id, qty_sold=1, created_by_user_id=owner_user.id, commit=True)

    med.particulars = "RENAMED NOW"
    db_session.commit()

    recent = sales_lookup_service.get_recent_sales(db_session, tenant.id, hours=24)
    assert len(recent) == 1
    row = recent[0]
    assert row["medicine_name"] == "OLD NAME"
    assert row["unit_mrp_snapshot"] == 30.0
    assert row["unit_cost_snapshot"] == 20.0
    assert row["line_total"] == 30.0
    assert row["line_profit"] == 10.0
    assert row["sale_invoice_id"] is not None
