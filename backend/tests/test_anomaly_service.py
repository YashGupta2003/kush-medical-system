"""Tests for anomaly_service.py — Pillar 6, Part 2 (Anomaly / Pilferage Detection)."""
from datetime import datetime, timedelta

from app import models
from app.services import anomaly_service


def _rate_history(db_session, medicine, old_rate, new_rate, days_ago=1):
    rh = models.RateHistory(
        medicine_id=medicine.id, old_net_rate=old_rate, new_net_rate=new_rate,
        changed_at=datetime.utcnow() - timedelta(days=days_ago),
    )
    db_session.add(rh)
    db_session.commit()
    return rh


def _adjustment(db_session, medicine, change_qty, user_id=None, days_ago=1):
    row = models.StockLedger(
        medicine_id=medicine.id, change_qty=change_qty, resulting_balance=100,
        reason="manual_adjustment", created_by_user_id=user_id,
        created_at=datetime.utcnow() - timedelta(days=days_ago),
    )
    db_session.add(row)
    db_session.commit()
    return row


class TestPriceJumpAnomalies:
    def test_no_history_returns_empty_result(self, db_session):
        result = anomaly_service.detect_price_jump_anomalies(db_session)
        assert result["anomalies"] == []
        assert result["has_sufficient_data"] is False

    def test_below_min_samples_uses_zscore_fallback(self, db_session, sample_medicine):
        for old, new in [(100, 105), (100, 98), (100, 500)]:  # 3 samples, well below ML threshold
            _rate_history(db_session, sample_medicine, old, new)

        result = anomaly_service.detect_price_jump_anomalies(db_session)
        assert result["method"] == "zscore_fallback"
        assert result["has_sufficient_data"] is False
        # the 400% jump should stand out from the two ~stable ones
        assert any(a["pct_change"] > 100 for a in result["anomalies"])

    def test_uniform_changes_flag_nothing(self, db_session, sample_medicine):
        for i in range(3):
            _rate_history(db_session, sample_medicine, 100, 102, days_ago=i)
        result = anomaly_service.detect_price_jump_anomalies(db_session)
        assert result["anomalies"] == []

    def test_isolation_forest_used_once_enough_samples(self, db_session, sample_medicine):
        # 10 normal ~2% changes + 1 wild 900% outlier -> 11 samples, above MIN_SAMPLES_FOR_ISOLATION_FOREST
        for i in range(10):
            _rate_history(db_session, sample_medicine, 100, 101 + (i % 3), days_ago=i)
        _rate_history(db_session, sample_medicine, 100, 900, days_ago=20)

        result = anomaly_service.detect_price_jump_anomalies(db_session)
        assert result["has_sufficient_data"] is True
        assert result["method"] in ("isolation_forest", "zscore_fallback")  # falls back if sklearn isn't installed
        assert any(a["pct_change"] > 500 for a in result["anomalies"])

    def test_zero_old_rate_entries_are_excluded(self, db_session, sample_medicine):
        rh = models.RateHistory(medicine_id=sample_medicine.id, old_net_rate=0, new_net_rate=50, changed_at=datetime.utcnow())
        db_session.add(rh)
        db_session.commit()
        result = anomaly_service.detect_price_jump_anomalies(db_session)
        assert result["sample_size"] == 0


class TestStockAdjustmentAnomalies:
    def test_no_adjustments_returns_empty_result(self, db_session):
        result = anomaly_service.detect_stock_adjustment_anomalies(db_session)
        assert result["flagged_adjustments"] == []
        assert result["staff_summary"] == []

    def test_large_outlier_adjustment_is_flagged(self, db_session, sample_medicine):
        for i in range(5):
            _adjustment(db_session, sample_medicine, 3, days_ago=i)
        _adjustment(db_session, sample_medicine, 500, days_ago=10)   # wild outlier

        result = anomaly_service.detect_stock_adjustment_anomalies(db_session)
        assert any(a["change_qty"] == 500 for a in result["flagged_adjustments"])

    def test_small_negative_adjustments_are_never_flagged(self, db_session, sample_medicine):
        """Only unusually LARGE magnitude adjustments matter - routine small corrections should not be flagged."""
        for i in range(6):
            _adjustment(db_session, sample_medicine, -2, days_ago=i)
        result = anomaly_service.detect_stock_adjustment_anomalies(db_session)
        assert result["flagged_adjustments"] == []

    def test_unattributed_adjustments_counted_separately(self, db_session, sample_medicine):
        _adjustment(db_session, sample_medicine, 5, user_id=None)
        _adjustment(db_session, sample_medicine, 5, user_id=None)
        result = anomaly_service.detect_stock_adjustment_anomalies(db_session)
        assert result["unattributed_count"] == 2
        assert result["staff_summary"] == []

    def test_staff_summary_flags_over_represented_user(self, db_session, sample_medicine, owner_user, staff_user):
        # owner_user makes 8 adjustments, staff_user makes 1 -> owner is wildly over-represented
        for i in range(8):
            _adjustment(db_session, sample_medicine, 2, user_id=owner_user.id, days_ago=i)
        _adjustment(db_session, sample_medicine, 2, user_id=staff_user.id, days_ago=20)

        result = anomaly_service.detect_stock_adjustment_anomalies(db_session)
        owner_summary = next(s for s in result["staff_summary"] if s["user_id"] == owner_user.id)
        assert owner_summary["is_over_represented"] is True
        assert owner_summary["adjustment_count"] == 8

    def test_single_active_staff_member_is_never_flagged(self, db_session, sample_medicine, owner_user):
        """
        If only ONE staff account has ever made adjustments, "100% share"
        is meaningless (there's no one else to compare against) - must
        never be flagged just because it's the only account in the data.
        """
        for i in range(6):
            _adjustment(db_session, sample_medicine, 2, user_id=owner_user.id, days_ago=i)
        result = anomaly_service.detect_stock_adjustment_anomalies(db_session)
        summary = result["staff_summary"][0]
        assert summary["is_over_represented"] is False

    def test_few_adjustments_never_flag_even_if_disproportionate(self, db_session, sample_medicine, owner_user, staff_user):
        """A 2-vs-0 split shouldn't flag anyone - MIN_ADJUSTMENTS_TO_FLAG_STAFF guards against noise."""
        _adjustment(db_session, sample_medicine, 2, user_id=owner_user.id, days_ago=1)
        _adjustment(db_session, sample_medicine, 2, user_id=owner_user.id, days_ago=2)
        _adjustment(db_session, sample_medicine, 2, user_id=staff_user.id, days_ago=3)
        result = anomaly_service.detect_stock_adjustment_anomalies(db_session)
        assert all(not s["is_over_represented"] for s in result["staff_summary"])