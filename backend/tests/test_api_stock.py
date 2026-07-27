"""Integration tests for /stock endpoints - sales recording and the reorder list."""


def test_record_sale_via_api_decrements_stock(client, owner_headers, sample_medicine):
    response = client.post(
        "/stock/sales", json={"medicine_id": sample_medicine.id, "qty_sold": 2}, headers=owner_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["current_stock"] == float(sample_medicine.current_stock) - 2


def test_record_sale_rejects_zero_or_negative_quantity(client, owner_headers, sample_medicine):
    response = client.post(
        "/stock/sales", json={"medicine_id": sample_medicine.id, "qty_sold": -5}, headers=owner_headers,
    )
    assert response.status_code == 422


def test_record_sale_for_nonexistent_medicine_returns_404(client, owner_headers):
    response = client.post(
        "/stock/sales", json={"medicine_id": 999999, "qty_sold": 1}, headers=owner_headers,
    )
    assert response.status_code == 404


def test_stock_snapshot_endpoint(client, owner_headers, sample_medicine):
    response = client.get(f"/stock/medicine/{sample_medicine.id}/snapshot", headers=owner_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["medicine_id"] == sample_medicine.id
    assert body["current_stock"] == float(sample_medicine.current_stock)


def test_reorder_list_endpoint_returns_a_list(client, owner_headers):
    response = client.get("/stock/reorder-list", headers=owner_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_add_manual_reorder_item_via_api(client, owner_headers):
    response = client.post(
        "/stock/reorder-list/manual",
        json={"custom_name": "Test Reorder Item", "distributor_name_new": "Test Distributor", "quantity_needed": 3},
        headers=owner_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Test Reorder Item"
    assert body["source"] == "manual"

    reorder_list = client.get("/stock/reorder-list", headers=owner_headers).json()
    names = [item["name"] for group in reorder_list for item in group["items"]]
    assert "Test Reorder Item" in names


def test_manual_reorder_item_requires_name_or_medicine(client, owner_headers):
    response = client.post(
        "/stock/reorder-list/manual",
        json={"distributor_name_new": "Some Distributor"},
        headers=owner_headers,
    )
    assert response.status_code == 422


def test_update_low_stock_threshold(client, owner_headers, sample_medicine):
    response = client.patch(
        f"/stock/medicine/{sample_medicine.id}/threshold",
        json={"low_stock_threshold": 25},
        headers=owner_headers,
    )
    assert response.status_code == 200
    assert response.json()["low_stock_threshold"] == 25.0


def test_stock_endpoints_require_login(client, sample_medicine):
    response = client.get(f"/stock/medicine/{sample_medicine.id}/snapshot")
    assert response.status_code == 401