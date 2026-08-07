"""Tests for symptom_bot_service.py — Pillar 5, Part A.3."""
from app.services import symptom_bot_service, graph_service, composition_service
from app import models


def _seed_and_medicine(db_session):
    graph_service.seed_condition_edges(db_session)
    db_session.commit()
    med = models.Medicine(particulars="CROCIN 650", normalized_name="CROCIN 650", current_stock=10)
    db_session.add(med)
    db_session.commit()
    db_session.refresh(med)
    composition_service.set_medicine_composition(db_session, med.id, "Paracetamol 650mg")
    db_session.commit()
    return med


class TestMatching:
    def test_known_symptom_word_matches_its_condition(self, db_session):
        graph_service.seed_condition_edges(db_session)
        db_session.commit()
        matches = symptom_bot_service.match_symptoms_to_conditions(db_session, "I have a fever since morning")
        assert "Fever" in matches

    def test_unmatched_gibberish_returns_no_conditions(self, db_session):
        graph_service.seed_condition_edges(db_session)
        db_session.commit()
        matches = symptom_bot_service.match_symptoms_to_conditions(db_session, "asdkfjaslkdfj")
        assert matches == []

    def test_matching_is_case_insensitive(self, db_session):
        graph_service.seed_condition_edges(db_session)
        db_session.commit()
        assert symptom_bot_service.match_symptoms_to_conditions(db_session, "FEVER") == \
               symptom_bot_service.match_symptoms_to_conditions(db_session, "fever")


class TestAnswerSymptomQuery:
    def test_matched_query_includes_in_stock_suggestions(self, db_session):
        _seed_and_medicine(db_session)
        result = symptom_bot_service.answer_symptom_query(db_session, "I have fever")
        assert result["matched"] is True
        assert "Fever" in result["conditions"]
        assert any(s["particulars"] == "CROCIN 650" for s in result["suggestions"]["Fever"])

    def test_disclaimer_is_always_present_and_never_a_diagnosis(self, db_session):
        _seed_and_medicine(db_session)
        result = symptom_bot_service.answer_symptom_query(db_session, "I have fever")
        assert "not a diagnosis" in result["disclaimer"]
        assert result["disclaimer"] in result["reply"]

    def test_unmatched_query_still_returns_the_disclaimer(self, db_session):
        graph_service.seed_condition_edges(db_session)
        db_session.commit()
        result = symptom_bot_service.answer_symptom_query(db_session, "zzz nonsense zzz")
        assert result["matched"] is False
        assert "not a diagnosis" in result["disclaimer"]

    def test_matched_condition_with_no_stock_says_so_rather_than_omitting(self, db_session):
        graph_service.seed_condition_edges(db_session)
        db_session.commit()
        # No medicines exist at all - "Fever" matches but has zero in-stock suggestions.
        result = symptom_bot_service.answer_symptom_query(db_session, "fever")
        assert result["matched"] is True
        assert result["suggestions"]["Fever"] == []
        assert "nothing matching is currently in stock" in result["reply"]