"""
Pillar 6, Part 2 - Anomaly / Pilferage Detection.

Flags STATISTICALLY UNUSUAL patterns in two places this system already
tracks every event of: RateHistory (price changes) and StockLedger's
manual_adjustment entries (physical stock corrections). Deliberately
framed as "worth a look," never an accusation - see
detect_stock_adjustment_anomalies()'s staff_summary, which reports an
over-represented SHARE of adjustments, not "this person is stealing."
Innocent explanations (stock count corrections, breakage write-offs,
data-entry mistakes) are common and this module says nothing about which
explanation applies - it only says where to look.

Method: scikit-learn's IsolationForest, per pharma_roadmap.md, once
there's a reasonable sample size (MIN_SAMPLES_FOR_ISOLATION_FOREST).
Below that, a LEAVE-ONE-OUT z-score is used instead of a plain
group-inclusive z-score. This distinction matters and is worth stating
explicitly: with a plain z-score, an extreme outlier drags its own
sample's mean/std toward itself, which mathematically CAPS the highest
possible z-score at sqrt(n-1) for a group of n points - with only 3
points, no outlier, however extreme, can ever score above ~1.41, so a
threshold of 2.0 would silently never fire below ~5 samples. Leave-one-out
scoring (a form of Grubbs' test) instead compares each point against the
mean/std of every OTHER point, which is uncapped and correctly flags
extreme values even at very small sample sizes - exactly the range where
a small shop with 2-3 staff actually operates.

If scikit-learn itself isn't installed, the leave-one-out z-score
fallback is used automatically rather than the endpoint erroring.
"""
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app import models

MIN_SAMPLES_FOR_ISOLATION_FOREST = 8
MIN_ADJUSTMENTS_TO_FLAG_STAFF = 3         # never flag someone off 1-2 adjustments - too noisy to mean anything
OVER_REPRESENTATION_MULTIPLIER = 2.0      # flagged once someone's count is 2x the average of everyone ELSE
Z_SCORE_THRESHOLD = 2.0


def _try_isolation_forest(X: list[list[float]]):
    """Returns (predictions, scores) or None if scikit-learn isn't available."""
    try:
        from sklearn.ensemble import IsolationForest
    except ImportError:
        return None
    model = IsolationForest(n_estimators=150, contamination="auto", random_state=42)
    model.fit(X)
    predictions = model.predict(X)          # -1 = anomaly, 1 = normal
    scores = model.decision_function(X)     # lower = more anomalous
    return predictions, scores


def _leave_one_out_zscores(values: list[float]) -> dict[int, float]:
    """
    For each index i, computes z_i = (values[i] - mean(rest)) / std(rest),
    where "rest" is every OTHER value in the list. See module docstring
    for why this is used instead of a plain group-inclusive z-score.
    Indices where fewer than 2 "other" points exist (n < 3 total) are
    skipped - there's no meaningful spread to compare against.
    """
    n = len(values)
    scores: dict[int, float] = {}
    for i, v in enumerate(values):
        others = [values[j] for j in range(n) if j != i]
        if len(others) < 2:
            continue
        mean_o = sum(others) / len(others)
        # BUG FIX: Use sample variance (Bessel's correction) instead of population variance
        variance_o = sum((o - mean_o) ** 2 for o in others) / (len(others) - 1)
        std_o = math.sqrt(variance_o) or 1e-9
        scores[i] = (v - mean_o) / std_o
    return scores


# ---------------------------------------------------------------------------
# Price-jump anomalies
# ---------------------------------------------------------------------------
def detect_price_jump_anomalies(db: Session, days: int = 180) -> dict:
    """
    Every RateHistory entry in the window with a nonzero old_net_rate,
    scored for how unusual its percentage change is relative to every
    OTHER price change in the same window - a routine 3% GST-driven
    adjustment looks nothing like an accidental (or deliberate) 400% typo.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    raw_entries = (
        db.query(models.RateHistory)
        .filter(models.RateHistory.changed_at >= since)
        .filter(models.RateHistory.old_net_rate.isnot(None), models.RateHistory.new_net_rate.isnot(None))
        .all()
    )
    entries = [e for e in raw_entries if e.old_net_rate and float(e.old_net_rate) > 0]

    if not entries:
        return {
            "method": "none", "has_sufficient_data": False, "sample_size": 0,
            "anomalies": [], "reason": "No rate changes recorded in this window.",
        }

    pct_changes = [((float(e.new_net_rate) - float(e.old_net_rate)) / float(e.old_net_rate)) * 100 for e in entries]

    flagged_indices: set[int] = set()
    scores: dict[int, float] = {}
    method = "zscore_fallback"

    if len(entries) >= MIN_SAMPLES_FOR_ISOLATION_FOREST:
        result = _try_isolation_forest([[p] for p in pct_changes])
        if result:
            predictions, iso_scores = result
            method = "isolation_forest"
            for i, (pred, score) in enumerate(zip(predictions, iso_scores)):
                scores[i] = float(score)
                if pred == -1:
                    flagged_indices.add(i)

    if method == "zscore_fallback":
        scores = _leave_one_out_zscores(pct_changes)
        for i, z in scores.items():
            if abs(z) > Z_SCORE_THRESHOLD:
                flagged_indices.add(i)

    anomalies = []
    for i in sorted(flagged_indices, key=lambda idx: scores[idx]):
        e = entries[i]
        medicine = db.get(models.Medicine, e.medicine_id)
        anomalies.append({
            "rate_history_id": e.id, "medicine_id": e.medicine_id,
            "medicine_name": medicine.particulars if medicine else "Unknown",
            "old_rate": float(e.old_net_rate), "new_rate": float(e.new_net_rate),
            "pct_change": round(pct_changes[i], 1), "changed_at": e.changed_at,
            "score": round(scores[i], 3),
        })

    return {
        "method": method,
        "has_sufficient_data": len(entries) >= MIN_SAMPLES_FOR_ISOLATION_FOREST,
        "sample_size": len(entries),
        "anomalies": anomalies,
    }


# ---------------------------------------------------------------------------
# Stock-adjustment anomalies (individual + per-staff)
# ---------------------------------------------------------------------------
def detect_stock_adjustment_anomalies(db: Session, days: int = 90) -> dict:
    """
    Two layers:
      1. Per-adjustment: IsolationForest (or leave-one-out z-score
         fallback) over the absolute size of each manual_adjustment -
         flags individually unusual corrections (e.g. one 500-unit "fix"
         among many 2-3 unit ones).
      2. Per-staff: among adjustments that DO have a recorded
         created_by_user_id (older rows predating this feature won't -
         reported separately as unattributed_count), flags any staff
         account whose adjustment COUNT is more than
         OVER_REPRESENTATION_MULTIPLIER times the average count of every
         OTHER active staff member (not a share-of-total comparison -
         with only 2 staff, no one's share can ever exceed 100%, which
         made a share-based threshold mathematically impossible to
         trigger for the most common small-shop case). Only flagged once
         they have at least MIN_ADJUSTMENTS_TO_FLAG_STAFF adjustments on
         record - never off one or two corrections, which is completely
         normal.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(models.StockLedger)
        .filter(models.StockLedger.reason == "manual_adjustment", models.StockLedger.created_at >= since)
        .all()
    )

    if not rows:
        return {
            "method": "none", "has_sufficient_data": False, "sample_size": 0,
            "flagged_adjustments": [], "staff_summary": [], "unattributed_count": 0,
            "reason": "No manual stock adjustments recorded in this window.",
        }

    magnitudes = [abs(float(r.change_qty)) for r in rows]
    flagged_indices: set[int] = set()
    scores: dict[int, float] = {}
    method = "zscore_fallback"

    if len(rows) >= MIN_SAMPLES_FOR_ISOLATION_FOREST:
        result = _try_isolation_forest([[m] for m in magnitudes])
        if result:
            predictions, iso_scores = result
            method = "isolation_forest"
            for i, (pred, score) in enumerate(zip(predictions, iso_scores)):
                scores[i] = float(score)
                if pred == -1:
                    flagged_indices.add(i)

    if method == "zscore_fallback":
        scores = _leave_one_out_zscores(magnitudes)
        for i, z in scores.items():
            if z > Z_SCORE_THRESHOLD:   # one-sided - only unusually LARGE adjustments matter here
                flagged_indices.add(i)

    flagged_adjustments = []
    for i in sorted(flagged_indices, key=lambda idx: -scores[idx]):
        r = rows[i]
        medicine = db.get(models.Medicine, r.medicine_id)
        user = db.get(models.User, r.created_by_user_id) if r.created_by_user_id else None
        flagged_adjustments.append({
            "stock_ledger_id": r.id, "medicine_id": r.medicine_id,
            "medicine_name": medicine.particulars if medicine else "Unknown",
            "change_qty": float(r.change_qty), "resulting_balance": float(r.resulting_balance),
            "note": r.note, "created_by_user_id": r.created_by_user_id,
            "created_by_username": user.username if user else None,
            "created_at": r.created_at, "score": round(scores[i], 3),
        })

    attributed = [r for r in rows if r.created_by_user_id is not None]
    unattributed_count = len(rows) - len(attributed)

    staff_summary = []
    if attributed:
        counts: dict[int, int] = {}
        for r in attributed:
            counts[r.created_by_user_id] = counts.get(r.created_by_user_id, 0) + 1
        active_staff = len(counts)
        total = len(attributed)

        for user_id, count in sorted(counts.items(), key=lambda kv: -kv[1]):
            share = count / total
            is_over = False
            if count >= MIN_ADJUSTMENTS_TO_FLAG_STAFF and active_staff > 1:
                others_total = total - count
                avg_of_others = others_total / (active_staff - 1)
                is_over = avg_of_others > 0 and count > avg_of_others * OVER_REPRESENTATION_MULTIPLIER
            user = db.get(models.User, user_id)
            staff_summary.append({
                "user_id": user_id, "username": user.username if user else "Unknown",
                "adjustment_count": count, "share_pct": round(share * 100, 1),
                "is_over_represented": is_over,
            })

    return {
        "method": method,
        "has_sufficient_data": len(rows) >= MIN_SAMPLES_FOR_ISOLATION_FOREST,
        "sample_size": len(rows),
        "flagged_adjustments": flagged_adjustments,
        "staff_summary": staff_summary,
        "unattributed_count": unattributed_count,
    }