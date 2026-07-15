"""
Turns raw bill-line fields into the one number that matters:
"how much did this item actually cost the shop, per unit/strip".

Formula (matches how your distributors' invoices are structured):

    gross            = rate * qty
    after_discount_1 = gross * (1 - discount_pct/100)
    after_discount_2 = after_discount_1 * (1 - special_discount_pct/100)   # compounding, not additive
    net_landed       = after_discount_2 * (1 + gst_pct/100)
    effective_units  = qty + free_qty
    cost_per_unit     = net_landed / effective_units

Notes:
- discount_pct and special_discount_pct compound (layered), matching what we
  saw on the Kaiser Drugs and Verma Bros / Rathore Medicos bills (e.g. a flat
  discount followed by an additional %, or two separate "S.Dis%"/"Dis%" columns).
- If a bill already prints CGST + SGST separately instead of one GST%, pass
  gst_pct = cgst_pct + sgst_pct (the router does this before calling here).
- free_qty defaults to 0 when a bill has no "Free" column.
"""
from decimal import Decimal, ROUND_HALF_UP


def _d(value) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def compute_cost_per_unit(
    rate: float,
    qty: float,
    discount_pct: float = 0,
    special_discount_pct: float = 0,
    gst_pct: float = 0,
    free_qty: float = 0,
) -> float:
    rate_d = _d(rate)
    qty_d = _d(qty)
    disc1 = _d(discount_pct) / Decimal("100")
    disc2 = _d(special_discount_pct) / Decimal("100")
    gst = _d(gst_pct) / Decimal("100")
    free_d = _d(free_qty)

    effective_units = qty_d + free_d
    if effective_units <= 0:
        return 0.0

    gross = rate_d * qty_d
    after_discount_1 = gross * (Decimal("1") - disc1)
    after_discount_2 = after_discount_1 * (Decimal("1") - disc2)
    net_landed = after_discount_2 * (Decimal("1") + gst)

    cost_per_unit = net_landed / effective_units
    return float(cost_per_unit.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def cross_check_amount(
    rate: float,
    qty: float,
    discount_pct: float = 0,
    special_discount_pct: float = 0,
    gst_pct: float = 0,
) -> float:
    """
    Recomputes the line's total billed amount (before dividing by units) so it
    can be compared against the printed 'Amount' column, as a sanity check that
    OCR read the numbers correctly. Large mismatches should be flagged to the
    user during review rather than silently trusted.
    """
    rate_d = _d(rate)
    qty_d = _d(qty)
    disc1 = _d(discount_pct) / Decimal("100")
    disc2 = _d(special_discount_pct) / Decimal("100")
    gst = _d(gst_pct) / Decimal("100")

    gross = rate_d * qty_d
    after_discount_1 = gross * (Decimal("1") - disc1)
    after_discount_2 = after_discount_1 * (Decimal("1") - disc2)
    net_landed = after_discount_2 * (Decimal("1") + gst)
    return float(net_landed.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
