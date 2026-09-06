"""
Integration tests for the medicines endpoints: paginated search, the
Staff-can't-see-cost-price rule, and barcode lookup/assignment.
"""


def test_staff_cannot_see_cost_price_in_search_results(client, staff_headers, sample_medicine):
    response = client.get("/medicines", headers=staff_headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) > 0
    assert all(item["net_rate"] is None for item in items)


def test_owner_can_see_cost_price_in_search_results(client, owner_headers, sample_medicine):
    response = client.get("/medicines", headers=owner_headers)
    assert response.status_code == 200
    items = response.json()["items"]
    matching = [i for i in items if i["id"] == sample_medicine.id]
    assert len(matching) == 1
    assert matching[0]["net_rate"] is not None


def test_search_filters_by_query_text(client, owner_headers, sample_medicine):
    response = client.get("/medicines?q=AMLOKIND", headers=owner_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert any(item["id"] == sample_medicine.id for item in body["items"])


def test_search_with_no_match_returns_empty_list(client, owner_headers, sample_medicine):
    response = client.get("/medicines?q=DEFINITELY_NOT_A_REAL_MEDICINE_NAME_XYZ", headers=owner_headers)
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_barcode_lookup_for_unknown_code_returns_found_false(client, owner_headers):
    response = client.get("/medicines/barcode/UNKNOWN123456", headers=owner_headers)
    assert response.status_code == 200
    assert response.json()["found"] is False


def test_assign_and_then_lookup_barcode(client, owner_headers, sample_medicine):
    assign_response = client.patch(
        f"/medicines/{sample_medicine.id}/barcode",
        json={"barcode": "8901234567890"},
        headers=owner_headers,
    )
    assert assign_response.status_code == 200
    assert assign_response.json()["barcode"] == "8901234567890"

    lookup_response = client.get("/medicines/barcode/8901234567890", headers=owner_headers)
    assert lookup_response.status_code == 200
    body = lookup_response.json()
    assert body["found"] is True
    assert body["medicine"]["id"] == sample_medicine.id
    assert body["stock"] is not None   # scan result includes live stock snapshot


def test_cannot_assign_the_same_barcode_to_two_medicines(client, owner_headers, sample_medicine, db_session):
    from app import models
    second_medicine = models.Medicine(tenant_id=1, particulars="SECOND MEDICINE", normalized_name="SECOND MEDICINE", current_stock=0)
    db_session.add(second_medicine)
    db_session.commit()
    db_session.refresh(second_medicine)

    client.patch(f"/medicines/{sample_medicine.id}/barcode", json={"barcode": "1112223334445"}, headers=owner_headers)
    clash_response = client.patch(
        f"/medicines/{second_medicine.id}/barcode", json={"barcode": "1112223334445"}, headers=owner_headers,
    )
    assert clash_response.status_code == 400