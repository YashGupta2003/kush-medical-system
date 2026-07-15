"""
Ground-truth tests using real line items copied from the bills you uploaded
(Hari Krishna Distributor invoice, 28-06-2026). Good evidence for your
project report/viva that the cost engine matches real invoice math.
"""
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.services.cost_calculator import compute_cost_per_unit, cross_check_amount


def test_amlovent_at_tab():
    # QTY 20, Rate 8.00, Dis 4.76%, GST 5%, printed Amount = 160.00
    amount = cross_check_amount(rate=8.00, qty=20, discount_pct=4.76, gst_pct=5.00)
    assert abs(amount - 160.00) < 0.5

    cost_per_unit = compute_cost_per_unit(rate=8.00, qty=20, discount_pct=4.76, gst_pct=5.00, free_qty=0)
    assert abs(cost_per_unit - 8.00) < 0.1


def test_bactofix_dry_syp():
    # QTY 3.00, Rate 24.00, Dis 4.76%, GST 5%, printed Amount = 72.00
    amount = cross_check_amount(rate=24.00, qty=3, discount_pct=4.76, gst_pct=5.00)
    assert abs(amount - 72.00) < 0.5


def test_meftadol_forte_60ml():
    # QTY 4.00, Rate 22.00, Dis 4.76%, GST 5%, printed Amount = 88.00
    amount = cross_check_amount(rate=22.00, qty=4, discount_pct=4.76, gst_pct=5.00)
    assert abs(amount - 88.00) < 0.5


def test_free_quantity_reduces_cost_per_unit():
    # Same paid amount, but with free units, cost per unit should be lower than rate.
    no_free = compute_cost_per_unit(rate=100, qty=10, gst_pct=5, free_qty=0)
    with_free = compute_cost_per_unit(rate=100, qty=10, gst_pct=5, free_qty=2)
    assert with_free < no_free


def test_layered_discounts_compound_not_additive():
    # 60% then 37.5% (as seen on the Kaiser Drugs bill) should NOT equal a flat 97.5% off.
    result = compute_cost_per_unit(rate=87.28, qty=40, discount_pct=60, special_discount_pct=37.5, gst_pct=5)
    naive_additive = 87.28 * 40 * (1 - 0.975) * 1.05 / 40
    assert result != round(naive_additive, 2)
    assert result > 0
