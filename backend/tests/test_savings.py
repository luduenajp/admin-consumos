"""Tests for Saving CRUD and API endpoints."""
from datetime import date

import pytest

from app.crud import (
    create_saving,
    create_saving_snapshot,
    delete_saving,
    delete_saving_snapshot,
    list_saving_snapshots,
    list_savings,
    update_saving,
)
from app.models import CurrencyCode
from app.schemas import SavingCreate, SavingSnapshotCreate, SavingUpdate


class TestSavingCRUD:
    def test_create_and_list(self, session, two_persons):
        alice, _ = two_persons
        saving = create_saving(
            session=session,
            payload=SavingCreate(
                person_id=alice.id,
                investment_type="FCI",
                institution="Banco Nación",
                currency=CurrencyCode.ARS,
            ),
        )
        assert saving.id is not None
        assert saving.investment_type == "FCI"
        assert saving.institution == "Banco Nación"
        assert saving.currency == CurrencyCode.ARS
        assert saving.notes is None

        rows = list_savings(session=session)
        assert len(rows) == 1
        s, current_amount, current_date = rows[0]
        assert s.id == saving.id
        assert current_amount is None  # no snapshots yet
        assert current_date is None

    def test_create_invalid_person(self, session):
        with pytest.raises(ValueError, match="Person not found"):
            create_saving(
                session=session,
                payload=SavingCreate(
                    person_id=9999,
                    investment_type="FCI",
                    institution="MP",
                    currency=CurrencyCode.USD,
                ),
            )

    def test_update_saving(self, session, two_persons):
        alice, _ = two_persons
        saving = create_saving(
            session=session,
            payload=SavingCreate(
                person_id=alice.id,
                investment_type="Bono",
                institution="BNA",
                currency=CurrencyCode.ARS,
            ),
        )
        updated = update_saving(
            session=session,
            saving_id=saving.id,
            payload=SavingUpdate(institution="Galicia", notes="Actualizado"),
        )
        assert updated.institution == "Galicia"
        assert updated.notes == "Actualizado"
        assert updated.investment_type == "Bono"  # unchanged

    def test_update_not_found(self, session):
        with pytest.raises(ValueError, match="not found"):
            update_saving(session=session, saving_id=9999, payload=SavingUpdate(notes="X"))

    def test_list_savings_returns_latest_snapshot(self, session, two_persons):
        alice, _ = two_persons
        saving = create_saving(
            session=session,
            payload=SavingCreate(
                person_id=alice.id,
                investment_type="CDAR",
                institution="MP",
                currency=CurrencyCode.ARS,
            ),
        )
        # Add two snapshots — latest should be returned
        create_saving_snapshot(
            session=session,
            saving_id=saving.id,
            payload=SavingSnapshotCreate(date=date(2025, 1, 1), amount=100_000),
        )
        create_saving_snapshot(
            session=session,
            saving_id=saving.id,
            payload=SavingSnapshotCreate(date=date(2025, 3, 1), amount=150_000),
        )

        rows = list_savings(session=session)
        assert len(rows) == 1
        _, current_amount, current_date = rows[0]
        assert current_amount == 150_000
        assert current_date == date(2025, 3, 1)

    def test_delete_saving_cascades_snapshots(self, session, two_persons):
        alice, _ = two_persons
        saving = create_saving(
            session=session,
            payload=SavingCreate(
                person_id=alice.id,
                investment_type="FCI",
                institution="BNA",
                currency=CurrencyCode.ARS,
            ),
        )
        create_saving_snapshot(
            session=session,
            saving_id=saving.id,
            payload=SavingSnapshotCreate(date=date(2025, 1, 1), amount=50_000),
        )
        saving_id = saving.id

        delete_saving(session=session, saving_id=saving_id)

        rows = list_savings(session=session)
        assert len(rows) == 0

        snapshots = list_saving_snapshots(session=session, saving_id=saving_id)
        assert len(snapshots) == 0

    def test_delete_not_found(self, session):
        with pytest.raises(ValueError, match="not found"):
            delete_saving(session=session, saving_id=9999)

    def test_snapshots_ordered_by_date(self, session, two_persons):
        alice, _ = two_persons
        saving = create_saving(
            session=session,
            payload=SavingCreate(
                person_id=alice.id,
                investment_type="Bono",
                institution="BNA",
                currency=CurrencyCode.USD,
            ),
        )
        create_saving_snapshot(session=session, saving_id=saving.id, payload=SavingSnapshotCreate(date=date(2025, 3, 1), amount=200))
        create_saving_snapshot(session=session, saving_id=saving.id, payload=SavingSnapshotCreate(date=date(2025, 1, 1), amount=100))
        create_saving_snapshot(session=session, saving_id=saving.id, payload=SavingSnapshotCreate(date=date(2025, 2, 1), amount=150))

        snapshots = list_saving_snapshots(session=session, saving_id=saving.id)
        amounts = [s.amount for s in snapshots]
        assert amounts == [100, 150, 200]

    def test_delete_snapshot(self, session, two_persons):
        alice, _ = two_persons
        saving = create_saving(
            session=session,
            payload=SavingCreate(
                person_id=alice.id,
                investment_type="FCI",
                institution="MP",
                currency=CurrencyCode.ARS,
            ),
        )
        snap = create_saving_snapshot(
            session=session,
            saving_id=saving.id,
            payload=SavingSnapshotCreate(date=date(2025, 1, 1), amount=10_000),
        )
        delete_saving_snapshot(session=session, snapshot_id=snap.id)
        snapshots = list_saving_snapshots(session=session, saving_id=saving.id)
        assert len(snapshots) == 0

    def test_delete_snapshot_not_found(self, session):
        with pytest.raises(ValueError, match="not found"):
            delete_saving_snapshot(session=session, snapshot_id=9999)


class TestSavingAPI:
    def test_create_saving_endpoint(self, client, two_persons):
        alice, _ = two_persons
        resp = client.post(
            "/api/savings",
            json={
                "person_id": alice.id,
                "investment_type": "FCI",
                "institution": "Banco Nación",
                "currency": "ARS",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["investment_type"] == "FCI"
        assert data["currency"] == "ARS"
        assert data["current_amount"] is None

    def test_list_savings_endpoint(self, client, two_persons):
        alice, _ = two_persons
        client.post(
            "/api/savings",
            json={"person_id": alice.id, "investment_type": "FCI", "institution": "BNA", "currency": "ARS"},
        )
        resp = client.get("/api/savings")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_create_saving_invalid_person(self, client):
        resp = client.post(
            "/api/savings",
            json={"person_id": 9999, "investment_type": "FCI", "institution": "BNA", "currency": "ARS"},
        )
        assert resp.status_code == 400

    def test_delete_saving_endpoint(self, client, two_persons):
        alice, _ = two_persons
        resp = client.post(
            "/api/savings",
            json={"person_id": alice.id, "investment_type": "Bono", "institution": "MP", "currency": "USD"},
        )
        saving_id = resp.json()["id"]

        resp = client.delete(f"/api/savings/{saving_id}")
        assert resp.status_code == 204

        resp = client.get("/api/savings")
        assert len(resp.json()) == 0

    def test_delete_saving_not_found(self, client):
        resp = client.delete("/api/savings/9999")
        assert resp.status_code == 404

    def test_create_snapshot_endpoint(self, client, two_persons):
        alice, _ = two_persons
        resp = client.post(
            "/api/savings",
            json={"person_id": alice.id, "investment_type": "FCI", "institution": "BNA", "currency": "ARS"},
        )
        saving_id = resp.json()["id"]

        resp = client.post(
            f"/api/savings/{saving_id}/snapshots",
            json={"date": "2025-03-01", "amount": 200000},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["amount"] == 200000
        assert data["date"] == "2025-03-01"

    def test_get_snapshots_endpoint(self, client, two_persons):
        alice, _ = two_persons
        resp = client.post(
            "/api/savings",
            json={"person_id": alice.id, "investment_type": "FCI", "institution": "BNA", "currency": "ARS"},
        )
        saving_id = resp.json()["id"]

        client.post(f"/api/savings/{saving_id}/snapshots", json={"date": "2025-01-01", "amount": 100000})
        client.post(f"/api/savings/{saving_id}/snapshots", json={"date": "2025-03-01", "amount": 150000})

        resp = client.get(f"/api/savings/{saving_id}/snapshots")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        # Ordered by date ASC
        assert data[0]["amount"] == 100000
        assert data[1]["amount"] == 150000

    def test_get_savings_includes_current_amount(self, client, two_persons):
        alice, _ = two_persons
        resp = client.post(
            "/api/savings",
            json={"person_id": alice.id, "investment_type": "FCI", "institution": "BNA", "currency": "ARS"},
        )
        saving_id = resp.json()["id"]

        client.post(f"/api/savings/{saving_id}/snapshots", json={"date": "2025-01-01", "amount": 100000})
        client.post(f"/api/savings/{saving_id}/snapshots", json={"date": "2025-03-01", "amount": 200000})

        resp = client.get("/api/savings")
        data = resp.json()
        assert data[0]["current_amount"] == 200000
        assert data[0]["current_amount_date"] == "2025-03-01"

    def test_delete_snapshot_endpoint(self, client, two_persons):
        alice, _ = two_persons
        resp = client.post(
            "/api/savings",
            json={"person_id": alice.id, "investment_type": "FCI", "institution": "BNA", "currency": "ARS"},
        )
        saving_id = resp.json()["id"]

        resp = client.post(f"/api/savings/{saving_id}/snapshots", json={"date": "2025-01-01", "amount": 50000})
        snapshot_id = resp.json()["id"]

        resp = client.delete(f"/api/savings/{saving_id}/snapshots/{snapshot_id}")
        assert resp.status_code == 204

        resp = client.get(f"/api/savings/{saving_id}/snapshots")
        assert len(resp.json()) == 0

    def test_patch_saving_endpoint(self, client, two_persons):
        alice, _ = two_persons
        resp = client.post(
            "/api/savings",
            json={"person_id": alice.id, "investment_type": "FCI", "institution": "BNA", "currency": "ARS"},
        )
        saving_id = resp.json()["id"]

        resp = client.patch(f"/api/savings/{saving_id}", json={"notes": "Updated notes"})
        assert resp.status_code == 200
        assert resp.json()["notes"] == "Updated notes"
