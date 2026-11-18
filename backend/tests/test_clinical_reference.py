"""Tests for database-backed clinical references and their JSON fallback."""
import pytest
from sqlalchemy.exc import IntegrityError

from app import models
from app.services import (
    clinical_reference_service,
    composition_service,
    graph_service,
    pos_service,
    symptom_bot_service,
)


def test_empty_database_and_missing_session_use_json_baseline(db_session):
    without_session = clinical_reference_service.get_clinical_reference_data()
    empty_database = clinical_reference_service.get_clinical_reference_data(db_session)

    assert without_session["salt_conditions"]
    assert without_session["drug_interactions"]
    assert empty_database == without_session
    assert graph_service.check_interactions(db_session, ["Warfarin", "Aspirin"])
    assert "Fever" in symptom_bot_service.match_symptoms_to_conditions(db_session, "fever")


def test_seed_is_idempotent(db_session):
    first = clinical_reference_service.seed_clinical_data(db_session)
    db_session.commit()
    counts_after_first_seed = (
        db_session.query(models.SaltCondition).count(),
        db_session.query(models.DrugInteraction).count(),
    )

    second = clinical_reference_service.seed_clinical_data(db_session)
    db_session.commit()

    assert first["salt_conditions"] > 0
    assert first["drug_interactions"] > 0
    assert counts_after_first_seed == (
        db_session.query(models.SaltCondition).count(),
        db_session.query(models.DrugInteraction).count(),
    )
    assert second == {"salt_conditions": 0, "drug_interactions": 0}


def test_dynamic_interaction_is_used_by_pos_checker(db_session, tenant):
    db_session.add(models.DrugInteraction(
        salt_a="Reference Alpha", salt_b="Reference Beta",
        severity="high", note="Synthetic test rule",
    ))
    medicines = [
        models.Medicine(
            tenant_id=tenant.id, particulars=name, normalized_name=name.upper(),
            current_stock=10,
        )
        for name in ("Reference Alpha Tablet", "Reference Beta Tablet")
    ]
    db_session.add_all(medicines)
    db_session.commit()
    for medicine, composition in zip(
        medicines,
        ("Reference Alpha 10mg", "Reference Beta 10mg"),
    ):
        composition_service.set_medicine_composition(db_session, medicine.id, composition)
    db_session.commit()

    result = pos_service.check_cart_interactions(
        db_session,
        tenant.id,
        [{"medicine_id": medicine.id, "qty_sold": 1} for medicine in medicines],
    )

    assert result["has_interactions"] is True
    assert result["interactions"] == [{
        "salt_a": "REFERENCE ALPHA",
        "salt_b": "REFERENCE BETA",
        "severity": "high",
        "note": "Synthetic test rule",
    }]


def test_dynamic_salt_condition_is_used_by_symptom_bot(db_session, tenant):
    db_session.add(models.SaltCondition(
        salt_name="Reference Herb",
        conditions=["Synthetic Test Syndrome"],
    ))
    medicine = models.Medicine(
        tenant_id=tenant.id,
        particulars="Reference Herb Tablet",
        normalized_name="REFERENCE HERB TABLET",
        current_stock=10,
    )
    db_session.add(medicine)
    db_session.commit()
    composition_service.set_medicine_composition(
        db_session, medicine.id, "Reference Herb 10mg"
    )
    db_session.commit()

    result = symptom_bot_service.answer_symptom_query(
        db_session, "I have Synthetic Test Syndrome"
    )

    assert result["matched"] is True
    assert result["conditions"] == ["Synthetic Test Syndrome"]
    assert result["suggestions"]["Synthetic Test Syndrome"][0]["particulars"] == "Reference Herb Tablet"


def test_interaction_pair_is_normalized_and_unique(db_session):
    db_session.add(models.DrugInteraction(
        salt_a="Beta", salt_b="Alpha", severity="medium", note="First synthetic rule",
    ))
    db_session.commit()
    db_session.add(models.DrugInteraction(
        salt_a=" alpha ", salt_b="BETA", severity="medium", note="Duplicate synthetic rule",
    ))

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    row = db_session.query(models.DrugInteraction).one()
    assert (row.salt_a, row.salt_b) == ("ALPHA", "BETA")


def test_clinical_reference_crud_is_owner_only_and_soft_deletes(client, db_session, owner_headers, staff_headers):
    payload = {
        "salt_a": "Demo Alpha",
        "salt_b": "Demo Beta",
        "severity": "HIGH",
        "note": "Synthetic API test rule",
    }
    created = client.post(
        "/v1/clinical-reference/drug-interactions",
        headers=owner_headers,
        json=payload,
    )
    assert created.status_code == 201
    record = created.json()
    assert (record["salt_a"], record["salt_b"]) == ("DEMO ALPHA", "DEMO BETA")

    denied = client.post(
        "/v1/clinical-reference/drug-interactions",
        headers=staff_headers,
        json=payload,
    )
    assert denied.status_code == 403

    duplicate = client.post(
        "/v1/clinical-reference/drug-interactions",
        headers=owner_headers,
        json={**payload, "salt_a": "Demo Beta", "salt_b": "Demo Alpha"},
    )
    assert duplicate.status_code == 409

    deleted = client.delete(
        f"/v1/clinical-reference/drug-interactions/{record['id']}",
        headers=owner_headers,
    )
    assert deleted.status_code == 200
    assert deleted.json()["is_active"] is False
    assert graph_service.check_interactions(db_session, ["DEMO ALPHA", "DEMO BETA"]) == []
