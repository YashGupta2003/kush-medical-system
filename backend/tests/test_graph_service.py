"""Tests for graph_service.py - the PharmaGraph knowledge graph (Pillar 1)."""
from app.services import graph_service, composition_service
from app import models


def _medicine(db_session, name, composition=None, stock=10):
    med = models.Medicine(particulars=name, normalized_name=name.upper(), current_stock=stock)
    db_session.add(med)
    db_session.commit()
    db_session.refresh(med)
    if composition:
        composition_service.set_medicine_composition(db_session, med.id, composition)
        db_session.commit()
    return med


class TestEdgePrimitives:
    def test_add_edge_and_get_neighbors_out(self, db_session):
        graph_service.add_edge(db_session, "medicine", 1, "CONTAINS", "salt", "PARACETAMOL")
        db_session.commit()

        neighbors = graph_service.get_neighbors(db_session, "medicine", 1, edge_type="CONTAINS", direction="out")
        assert len(neighbors) == 1
        assert neighbors[0].target_id == "PARACETAMOL"

    def test_get_neighbors_in_direction(self, db_session):
        graph_service.add_edge(db_session, "distributor", 5, "SUPPLIES", "medicine", 42)
        db_session.commit()

        neighbors = graph_service.get_neighbors(db_session, "medicine", 42, edge_type="SUPPLIES", direction="in")
        assert len(neighbors) == 1
        assert neighbors[0].source_id == "5"

    def test_replace_true_prevents_duplicate_edges_on_resave(self, db_session):
        graph_service.add_edge(db_session, "medicine", 1, "CONTAINS", "salt", "PARACETAMOL")
        db_session.commit()
        graph_service.add_edge(db_session, "medicine", 1, "CONTAINS", "salt", "PARACETAMOL")
        db_session.commit()

        neighbors = graph_service.get_neighbors(db_session, "medicine", 1, edge_type="CONTAINS")
        assert len(neighbors) == 1


class TestContainsSync:
    def test_sync_creates_edges_matching_medicine_salts(self, db_session):
        med = _medicine(db_session, "DOLO 650", "Paracetamol 650mg")
        # set_medicine_composition already calls sync internally - verify the edge exists
        neighbors = graph_service.get_neighbors(db_session, "medicine", med.id, edge_type="CONTAINS")
        assert len(neighbors) == 1
        assert neighbors[0].target_id == "PARACETAMOL"

    def test_resync_replaces_stale_edges(self, db_session):
        med = _medicine(db_session, "TEST MED", "Paracetamol 650mg")
        composition_service.set_medicine_composition(db_session, med.id, "Ibuprofen 400mg")
        db_session.commit()

        neighbors = graph_service.get_neighbors(db_session, "medicine", med.id, edge_type="CONTAINS")
        assert len(neighbors) == 1
        assert neighbors[0].target_id == "IBUPROFEN"


class TestSuppliesSync:
    def test_sync_supplies_edge(self, db_session, sample_medicine, sample_distributor):
        graph_service.sync_supplies_edge(db_session, sample_distributor.id, sample_medicine.id)
        db_session.commit()

        neighbors = graph_service.get_neighbors(db_session, "medicine", sample_medicine.id, edge_type="SUPPLIES", direction="in")
        assert len(neighbors) == 1
        assert neighbors[0].source_id == str(sample_distributor.id)

    def test_no_distributor_id_does_nothing(self, db_session, sample_medicine):
        graph_service.sync_supplies_edge(db_session, None, sample_medicine.id)
        db_session.commit()
        neighbors = graph_service.get_neighbors(db_session, "medicine", sample_medicine.id, edge_type="SUPPLIES", direction="in")
        assert len(neighbors) == 0


class TestSubstituteSync:
    def test_sync_writes_substitute_edges(self, db_session):
        crocin = _medicine(db_session, "CROCIN 650", "Paracetamol 650mg")
        dolo = _medicine(db_session, "DOLO 650", "Paracetamol 650mg")

        count = graph_service.sync_substitute_edges_for_medicine(db_session, crocin.id)
        db_session.commit()

        assert count == 1
        neighbors = graph_service.get_neighbors(db_session, "medicine", crocin.id, edge_type="SUBSTITUTES")
        assert neighbors[0].target_id == str(dolo.id)
        assert float(neighbors[0].weight) == 100.0

    def test_medicine_with_no_composition_yields_zero_edges(self, db_session, sample_medicine):
        count = graph_service.sync_substitute_edges_for_medicine(db_session, sample_medicine.id)
        assert count == 0


class TestInteractionSeedAndCheck:
    def test_seed_loads_real_data_file_without_error(self, db_session):
        count = graph_service.seed_interaction_edges(db_session)
        db_session.commit()
        assert count > 0   # the curated JSON file has real entries

    def test_known_interaction_pair_is_detected(self, db_session):
        graph_service.seed_interaction_edges(db_session)
        db_session.commit()

        results = graph_service.check_interactions(db_session, ["Warfarin", "Aspirin"])
        assert len(results) == 1
        assert results[0]["severity"] in ("high", "medium", "low")

    def test_unrelated_salts_have_no_interaction(self, db_session):
        graph_service.seed_interaction_edges(db_session)
        db_session.commit()

        results = graph_service.check_interactions(db_session, ["Paracetamol", "Cetirizine"])
        assert results == []

    def test_single_salt_cannot_interact_with_itself(self, db_session):
        assert graph_service.check_interactions(db_session, ["Paracetamol"]) == []


class TestConditionSeedAndLookup:
    def test_seed_loads_real_data_file_without_error(self, db_session):
        count = graph_service.seed_condition_edges(db_session)
        db_session.commit()
        assert count > 0

    def test_get_medicines_for_condition_finds_in_stock_matches(self, db_session):
        graph_service.seed_condition_edges(db_session)
        db_session.commit()
        _medicine(db_session, "CROCIN 650", "Paracetamol 650mg", stock=5)
        _medicine(db_session, "OUT OF STOCK PARA", "Paracetamol 500mg", stock=0)

        results = graph_service.get_medicines_for_condition(db_session, "Fever", in_stock_only=True)
        names = [r["particulars"] for r in results]
        assert "CROCIN 650" in names
        assert "OUT OF STOCK PARA" not in names

    def test_unknown_condition_returns_empty(self, db_session):
        graph_service.seed_condition_edges(db_session)
        db_session.commit()
        assert graph_service.get_medicines_for_condition(db_session, "NotARealCondition") == []


class TestMedicineGraph:
    def test_full_neighborhood_assembles_correctly(self, db_session, sample_distributor):
        graph_service.seed_interaction_edges(db_session)
        graph_service.seed_condition_edges(db_session)
        db_session.commit()

        crocin = _medicine(db_session, "CROCIN 650", "Paracetamol 650mg")
        dolo = _medicine(db_session, "DOLO 650", "Paracetamol 650mg")
        graph_service.sync_substitute_edges_for_medicine(db_session, crocin.id)
        graph_service.sync_supplies_edge(db_session, sample_distributor.id, crocin.id)
        db_session.commit()

        graph = graph_service.get_medicine_graph(db_session, crocin.id)

        assert graph["particulars"] == "CROCIN 650"
        assert any(c["salt"] == "PARACETAMOL" for c in graph["contains"])
        assert any(t["condition"] == "Fever" for t in graph["treats"])
        assert any(s["medicine_id"] == dolo.id for s in graph["substitutes"])
        assert any(d["distributor_id"] == sample_distributor.id for d in graph["supplied_by"])

    def test_nonexistent_medicine_returns_none(self, db_session):
        assert graph_service.get_medicine_graph(db_session, 999999) is None


class TestFullRebuild:
    def test_rebuild_runs_end_to_end_without_error(self, db_session, sample_distributor):
        _medicine(db_session, "CROCIN 650", "Paracetamol 650mg")
        db_session.commit()

        stats = graph_service.rebuild_full_graph(db_session)

        assert stats["contains"] >= 1
        assert stats["interactions"] > 0
        assert stats["treats"] > 0
