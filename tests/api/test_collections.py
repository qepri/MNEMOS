"""API tests for app/api/collections.py: CRUD + name-uniqueness conflict."""
import pytest

pytestmark = pytest.mark.api


def test_create_list_and_delete_collection(client, db_session):
    create_resp = client.post("/api/collections/", json={"name": "Research", "description": "papers"})
    assert create_resp.status_code == 201
    collection_id = create_resp.get_json()["id"]

    list_resp = client.get("/api/collections/")
    assert list_resp.status_code == 200
    assert any(c["id"] == collection_id for c in list_resp.get_json())

    delete_resp = client.delete(f"/api/collections/{collection_id}")
    assert delete_resp.status_code == 204

    list_resp_after = client.get("/api/collections/")
    assert all(c["id"] != collection_id for c in list_resp_after.get_json())


def test_create_collection_requires_name(client):
    resp = client.post("/api/collections/", json={"description": "no name"})
    assert resp.status_code == 400


def test_create_collection_name_conflict(client):
    client.post("/api/collections/", json={"name": "Duplicate"})
    resp = client.post("/api/collections/", json={"name": "Duplicate"})
    assert resp.status_code == 409


def test_update_missing_collection_returns_404(client):
    import uuid

    resp = client.put(f"/api/collections/{uuid.uuid4()}", json={"name": "x"})
    assert resp.status_code == 404
