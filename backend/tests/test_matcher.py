"""
Tests for matcher.py: pack-size extraction, weighted scoring (name + pack +
company), and the learned-mapping lookup/save that powers the 'learning'
feature (correct a match once, it's remembered forever after).
"""
import pytest

from app.services.matcher import (
    normalize, extract_pack_size, find_best_match,
    find_learned_mapping, save_learned_mapping,
)
from app import models


class TestNormalize:
    def test_uppercases_and_strips_punctuation(self):
        assert normalize("Amlokind-AT tab.") == "AMLOKIND AT TAB"

    def test_collapses_multiple_spaces(self):
        assert normalize("A    B   C") == "A B C"

    def test_empty_string_stays_empty(self):
        assert normalize("") == ""


class TestExtractPackSize:
    @pytest.mark.parametrize("text,expected", [
        ("10S", 10),
        ("15'S", 15),
        ("1*10", 10),
        ("10*10", 100),
        ("100 ML", None),   # a volume, not a pack count - deliberately ignored
        ("", None),
        (None, None),
    ])
    def test_various_formats(self, text, expected):
        assert extract_pack_size(text) == expected


class TestWeightedMatching:
    def test_exact_name_and_pack_match_scores_high_and_auto_links(self, db_session, sample_medicine):
        medicine, score, match_type = find_best_match(db_session, "AMLOKIND AT TAB 15S")
        assert match_type == "auto"
        assert medicine is not None
        assert medicine.id == sample_medicine.id
        assert score > 80

    def test_pack_mismatch_is_penalized_relative_to_pack_match(self, db_session, sample_medicine):
        """
        sample_medicine is packed 15S. The SAME name with a DIFFERENT pack
        size (10S) should score noticeably lower than the 15S version -
        this is the exact real-world case (Dolo 650 10S vs 15S) the
        weighted scoring was built to catch.
        """
        _, score_matching_pack, _ = find_best_match(db_session, "AMLOKIND AT TAB 15S")
        _, score_mismatched_pack, _ = find_best_match(db_session, "AMLOKIND AT TAB 10S")
        assert score_mismatched_pack < score_matching_pack

    def test_completely_different_name_is_unmatched(self, db_session, sample_medicine):
        medicine, score, match_type = find_best_match(db_session, "COMPLETELY UNRELATED PRODUCT XYZ 999")
        assert match_type == "unmatched"
        assert medicine is None

    def test_no_candidates_in_master_list_returns_unmatched(self, db_session):
        medicine, score, match_type = find_best_match(db_session, "ANYTHING AT ALL")
        assert match_type == "unmatched"
        assert medicine is None


class TestLearnedMappings:
    def test_learned_mapping_resolves_instantly_at_full_confidence(self, db_session, sample_medicine, sample_distributor):
        """
        Simulates the real workflow: OCR reads a distributor's consistent
        misspelling/abbreviation, the user manually links it once, and every
        future bill with that exact raw text from that distributor should
        resolve instantly without relying on fuzzy text similarity at all.
        """
        save_learned_mapping(
            db_session, raw_name="AMLOKIN-TYPO", medicine_id=sample_medicine.id,
            distributor_id=sample_distributor.id,
        )
        db_session.commit()

        medicine, score, match_type = find_best_match(
            db_session, "AMLOKIN-TYPO", distributor_id=sample_distributor.id
        )
        assert match_type == "learned"
        assert score == 100.0
        assert medicine.id == sample_medicine.id

    def test_learned_mapping_is_distributor_scoped(self, db_session, sample_medicine, sample_distributor):
        other_distributor = models.Distributor(name="OTHER DISTRIBUTOR")
        db_session.add(other_distributor)
        db_session.commit()
        db_session.refresh(other_distributor)

        save_learned_mapping(
            db_session, raw_name="DISTRIBUTOR-SPECIFIC-CODE", medicine_id=sample_medicine.id,
            distributor_id=sample_distributor.id,
        )
        db_session.commit()

        # A different distributor shouldn't inherit this distributor-specific mapping.
        result = find_learned_mapping(db_session, "DISTRIBUTOR-SPECIFIC-CODE", other_distributor.id)
        assert result is None

    def test_general_mapping_works_as_fallback_across_distributors(self, db_session, sample_medicine):
        save_learned_mapping(db_session, raw_name="GENERIC-CODE", medicine_id=sample_medicine.id, distributor_id=None)
        db_session.commit()

        result = find_learned_mapping(db_session, "GENERIC-CODE", distributor_id=12345)
        assert result is not None
        assert result.id == sample_medicine.id

    def test_saving_a_new_mapping_for_same_raw_name_updates_not_duplicates(self, db_session, sample_medicine, sample_distributor):
        another_medicine = models.Medicine(
            particulars="OTHER MEDICINE", normalized_name="OTHER MEDICINE", current_stock=0,
        )
        db_session.add(another_medicine)
        db_session.commit()
        db_session.refresh(another_medicine)

        save_learned_mapping(db_session, "SAME-CODE", sample_medicine.id, sample_distributor.id)
        db_session.commit()
        save_learned_mapping(db_session, "SAME-CODE", another_medicine.id, sample_distributor.id)
        db_session.commit()

        all_mappings = db_session.query(models.UserMapping).filter_by(raw_name="SAME-CODE").all()
        assert len(all_mappings) == 1
        assert all_mappings[0].medicine_id == another_medicine.id