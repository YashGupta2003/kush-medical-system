"""Tests for composition_service.py - the Substitute Medicine Suggestion feature."""
import pytest

from app.services.composition_service import (
    parse_composition, set_medicine_composition, find_substitutes, get_medicine_substitutes,
)
from app import models


class TestParseComposition:
    def test_single_salt_with_strength(self):
        result = parse_composition("Paracetamol 650mg")
        assert len(result) == 1
        assert result[0].salt_name == "PARACETAMOL"
        assert result[0].strength == "650MG"

    def test_combination_drug_splits_into_multiple_salts(self):
        result = parse_composition("Paracetamol 650mg + Caffeine 30mg")
        names = [r.salt_name for r in result]
        assert names == ["PARACETAMOL", "CAFFEINE"]
        assert result[1].strength == "30MG"

    def test_comma_and_and_separators_also_work(self):
        assert len(parse_composition("Amoxicillin 500mg, Clavulanic Acid 125mg")) == 2
        assert len(parse_composition("Amoxicillin 500mg and Clavulanic Acid 125mg")) == 2

    def test_salt_without_strength_still_parses(self):
        result = parse_composition("Paracetamol")
        assert result[0].salt_name == "PARACETAMOL"
        assert result[0].strength is None

    @pytest.mark.parametrize("text", [None, "", "   "])
    def test_empty_input_returns_empty_list(self, text):
        assert parse_composition(text) == []


class TestSetMedicineComposition:
    def test_saves_raw_text_and_parsed_salts(self, db_session, sample_medicine):
        set_medicine_composition(db_session, sample_medicine.id, "Amlodipine 5mg + Atenolol 50mg")
        db_session.commit()
        db_session.refresh(sample_medicine)

        assert sample_medicine.composition == "Amlodipine 5mg + Atenolol 50mg"
        salts = db_session.query(models.MedicineSalt).filter_by(medicine_id=sample_medicine.id).all()
        assert {s.salt_name for s in salts} == {"AMLODIPINE", "ATENOLOL"}

    def test_re_saving_replaces_old_salts_not_appends(self, db_session, sample_medicine):
        set_medicine_composition(db_session, sample_medicine.id, "Paracetamol 650mg")
        db_session.commit()
        set_medicine_composition(db_session, sample_medicine.id, "Ibuprofen 400mg")
        db_session.commit()

        salts = db_session.query(models.MedicineSalt).filter_by(medicine_id=sample_medicine.id).all()
        assert len(salts) == 1
        assert salts[0].salt_name == "IBUPROFEN"

    def test_returns_none_for_nonexistent_medicine(self, db_session):
        assert set_medicine_composition(db_session, 999999, "Paracetamol 650mg") is None


class TestFindSubstitutes:
    def _add_medicine(self, db_session, name, composition, stock):
        med = models.Medicine(
            particulars=name, normalized_name=name.upper(), current_stock=stock,
        )
        db_session.add(med)
        db_session.commit()
        db_session.refresh(med)
        set_medicine_composition(db_session, med.id, composition)
        db_session.commit()
        return med

    def test_exact_composition_match_is_ranked_first(self, db_session):
        crocin = self._add_medicine(db_session, "CROCIN 650", "Paracetamol 650mg", stock=0)
        dolo = self._add_medicine(db_session, "DOLO 650", "Paracetamol 650mg", stock=25)
        partial = self._add_medicine(db_session, "SOME COMBO", "Paracetamol 650mg + Caffeine 30mg", stock=10)

        results = find_substitutes(db_session, "Paracetamol 650mg", exclude_medicine_id=crocin.id)

        ids_in_order = [r["medicine_id"] for r in results]
        assert dolo.id in ids_in_order
        assert results[0]["medicine_id"] == dolo.id
        assert results[0]["match_type"] == "exact"

    def test_out_of_stock_medicines_are_excluded_by_default(self, db_session):
        self._add_medicine(db_session, "OUT OF STOCK BRAND", "Paracetamol 650mg", stock=0)
        results = find_substitutes(db_session, "Paracetamol 650mg")
        assert results == []

    def test_in_stock_only_false_includes_out_of_stock(self, db_session):
        self._add_medicine(db_session, "OUT OF STOCK BRAND", "Paracetamol 650mg", stock=0)
        results = find_substitutes(db_session, "Paracetamol 650mg", in_stock_only=False)
        assert len(results) == 1

    def test_unrelated_salt_returns_no_results(self, db_session):
        self._add_medicine(db_session, "AMOX", "Amoxicillin 500mg", stock=10)
        results = find_substitutes(db_session, "Paracetamol 650mg")
        assert results == []

    def test_empty_query_returns_empty_list(self, db_session):
        assert find_substitutes(db_session, "") == []


class TestGetMedicineSubstitutes:
    def test_looks_up_own_composition_and_excludes_itself(self, db_session):
        crocin = self._add_medicine_helper(db_session, "CROCIN 650", "Paracetamol 650mg", stock=0)
        dolo = self._add_medicine_helper(db_session, "DOLO 650", "Paracetamol 650mg", stock=15)

        result = get_medicine_substitutes(db_session, crocin.id)

        assert result["medicine"]["particulars"] == "CROCIN 650"
        sub_ids = [s["medicine_id"] for s in result["substitutes"]]
        assert dolo.id in sub_ids
        assert crocin.id not in sub_ids

    def test_medicine_with_no_composition_returns_empty_substitutes(self, db_session, sample_medicine):
        result = get_medicine_substitutes(db_session, sample_medicine.id)
        assert result["substitutes"] == []
        assert result["medicine"]["composition"] is None

    def test_nonexistent_medicine_returns_none(self, db_session):
        result = get_medicine_substitutes(db_session, 999999)
        assert result["medicine"] is None

    def _add_medicine_helper(self, db_session, name, composition, stock):
        med = models.Medicine(particulars=name, normalized_name=name.upper(), current_stock=stock)
        db_session.add(med)
        db_session.commit()
        db_session.refresh(med)
        set_medicine_composition(db_session, med.id, composition)
        db_session.commit()
        return med
