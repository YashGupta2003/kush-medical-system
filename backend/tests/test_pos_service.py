"""Tests for pos_service.py - Pillar 3's point-of-sale safety guardrail."""
from app.services import pos_service, composition_service, graph_service
from app import models


def _medicine(db_session, tenant, name, composition, stock=50):
    med = models.Medicine(tenant_id=tenant.id, particulars=name, normalized_name=name.upper(), current_stock=stock)
    db_session.add(med)
    db_session.commit()
    db_session.refresh(med)
    composition_service.set_medicine_composition(db_session, med.id, composition)
    db_session.commit()
    return med


class TestCheckCartInteractions:
    def test_no_interaction_for_unrelated_medicines(self, db_session, tenant):
        graph_service.seed_interaction_edges(db_session)
        db_session.commit()
        a = _medicine(db_session, tenant, "PARA TAB", "Paracetamol 650mg")
        b = _medicine(db_session, tenant, "CETI TAB", "Cetirizine 10mg")

        result = pos_service.check_cart_interactions(
            db_session, tenant.id, [{"medicine_id": a.id, "qty_sold": 1}, {"medicine_id": b.id, "qty_sold": 1}],
        )
        assert result["has_interactions"] is False
        assert result["interactions"] == []
        assert len(result["items"]) == 2

    def test_known_interacting_pair_is_flagged(self, db_session, tenant):
        graph_service.seed_interaction_edges(db_session)
        db_session.commit()
        warfarin_med = _medicine(db_session, tenant, "WARF TAB", "Warfarin 5mg")
        aspirin_med = _medicine(db_session, tenant, "ASP TAB", "Aspirin 75mg")

        result = pos_service.check_cart_interactions(
            db_session, tenant.id,
            [{"medicine_id": warfarin_med.id, "qty_sold": 1}, {"medicine_id": aspirin_med.id, "qty_sold": 1}],
        )
        assert result["has_interactions"] is True
        assert len(result["interactions"]) == 1
        assert result["interactions"][0]["severity"] in ("high", "medium", "low")

    def test_single_item_cart_never_flags(self, db_session, tenant):
        graph_service.seed_interaction_edges(db_session)
        db_session.commit()
        warfarin_med = _medicine(db_session, tenant, "WARF TAB", "Warfarin 5mg")

        result = pos_service.check_cart_interactions(db_session, tenant.id, [{"medicine_id": warfarin_med.id, "qty_sold": 1}])
        assert result["has_interactions"] is False

    def test_medicine_with_no_composition_is_included_but_contributes_no_salts(self, db_session, tenant, sample_medicine):
        result = pos_service.check_cart_interactions(db_session, tenant.id, [{"medicine_id": sample_medicine.id, "qty_sold": 1}])
        assert result["items"][0]["salts"] == []

    def test_nonexistent_medicine_id_is_skipped_not_crashed(self, db_session, tenant):
        result = pos_service.check_cart_interactions(db_session, tenant.id, [{"medicine_id": 999999, "qty_sold": 1}])
        assert result["items"] == []
        assert result["has_interactions"] is False


class TestRecordCartSale:
    def test_blocks_without_override_when_interaction_found(self, db_session, tenant):
        graph_service.seed_interaction_edges(db_session)
        db_session.commit()
        warfarin_med = _medicine(db_session, tenant, "WARF TAB", "Warfarin 5mg")
        aspirin_med = _medicine(db_session, tenant, "ASP TAB", "Aspirin 75mg")

        result = pos_service.record_cart_sale(
            db_session, tenant.id,
            [{"medicine_id": warfarin_med.id, "qty_sold": 1}, {"medicine_id": aspirin_med.id, "qty_sold": 1}],
        )
        assert result["status"] == "needs_confirmation"
        assert result["results"] == []

        # stock must be untouched
        db_session.refresh(warfarin_med)
        db_session.refresh(aspirin_med)
        assert float(warfarin_med.current_stock) == 50.0
        assert float(aspirin_med.current_stock) == 50.0

    def test_proceeds_with_override_and_records_all_items(self, db_session, tenant):
        graph_service.seed_interaction_edges(db_session)
        db_session.commit()
        warfarin_med = _medicine(db_session, tenant, "WARF TAB", "Warfarin 5mg")
        aspirin_med = _medicine(db_session, tenant, "ASP TAB", "Aspirin 75mg")

        result = pos_service.record_cart_sale(
            db_session, tenant.id,
            [{"medicine_id": warfarin_med.id, "qty_sold": 2}, {"medicine_id": aspirin_med.id, "qty_sold": 3}],
            confirm_override=True,
        )
        assert result["status"] == "recorded"
        assert len(result["results"]) == 2

        db_session.refresh(warfarin_med)
        db_session.refresh(aspirin_med)
        assert float(warfarin_med.current_stock) == 48.0
        assert float(aspirin_med.current_stock) == 47.0

    def test_no_interaction_cart_records_without_needing_override(self, db_session, tenant):
        graph_service.seed_interaction_edges(db_session)
        db_session.commit()
        a = _medicine(db_session, tenant, "PARA TAB", "Paracetamol 650mg")
        b = _medicine(db_session, tenant, "CETI TAB", "Cetirizine 10mg")

        result = pos_service.record_cart_sale(
            db_session, tenant.id, [{"medicine_id": a.id, "qty_sold": 1}, {"medicine_id": b.id, "qty_sold": 1}],
        )
        assert result["status"] == "recorded"
        assert len(result["results"]) == 2

    def test_single_item_sale_always_records_directly(self, db_session, tenant, sample_medicine):
        result = pos_service.record_cart_sale(db_session, tenant.id, [{"medicine_id": sample_medicine.id, "qty_sold": 1}])
        assert result["status"] == "recorded"
        assert len(result["results"]) == 1