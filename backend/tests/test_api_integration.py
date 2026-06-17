"""Integration tests for the REST API endpoints via TestClient."""
from datetime import date


class TestHealthEndpoint:
    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


class TestPeopleEndpoints:
    def test_create_and_list(self, client):
        r = client.post("/api/people", json={"name": "Alice"})
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "Alice"
        assert "id" in data

        r2 = client.get("/api/people")
        assert r2.status_code == 200
        assert len(r2.json()) == 1


class TestCardsEndpoints:
    def test_create_card_valid_person(self, client):
        person = client.post("/api/people", json={"name": "Bob"}).json()
        r = client.post(
            "/api/cards",
            json={"name": "Visa", "provider": "visa", "owner_person_id": person["id"]},
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Visa"

    def test_create_card_invalid_person_returns_400(self, client):
        r = client.post(
            "/api/cards",
            json={"name": "Visa", "provider": "visa", "owner_person_id": 9999},
        )
        assert r.status_code == 400

    def test_list_cards(self, client):
        person = client.post("/api/people", json={"name": "Carlos"}).json()
        client.post(
            "/api/cards",
            json={"name": "MC", "provider": "mastercard", "owner_person_id": person["id"]},
        )
        r = client.get("/api/cards")
        assert r.status_code == 200
        assert len(r.json()) >= 1


class TestPurchasesEndpoints:
    def _setup(self, client):
        person = client.post("/api/people", json={"name": "Alice"}).json()
        card = client.post(
            "/api/cards",
            json={"name": "Visa", "provider": "visa", "owner_person_id": person["id"]},
        ).json()
        return person, card

    def test_create_purchase(self, client):
        _, card = self._setup(client)
        r = client.post(
            "/api/purchases",
            json={
                "card_id": card["id"],
                "purchase_date": "2025-01-15",
                "description": "Test Purchase",
                "currency": "ARS",
                "amount_original": 50000,
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["description"] == "test purchase"

    def test_create_purchase_invalid_card_returns_400(self, client):
        r = client.post(
            "/api/purchases",
            json={
                "card_id": 9999,
                "purchase_date": "2025-01-15",
                "description": "Bad",
                "currency": "ARS",
                "amount_original": 1000,
            },
        )
        assert r.status_code == 400

    def test_list_purchases_paginated(self, client):
        _, card = self._setup(client)
        for i in range(3):
            client.post(
                "/api/purchases",
                json={
                    "card_id": card["id"],
                    "purchase_date": "2025-01-15",
                    "description": f"Purchase {i}",
                    "currency": "ARS",
                    "amount_original": 1000,
                },
            )
        r = client.get("/api/purchases")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 3
        assert "items" in data

    def test_delete_purchase(self, client):
        _, card = self._setup(client)
        created = client.post(
            "/api/purchases",
            json={
                "card_id": card["id"],
                "purchase_date": "2025-01-15",
                "description": "To Delete",
                "currency": "ARS",
                "amount_original": 5000,
            },
        ).json()
        r = client.delete(f"/api/purchases/{created['id']}")
        assert r.status_code == 204

    def test_delete_nonexistent_returns_404(self, client):
        r = client.delete("/api/purchases/99999")
        assert r.status_code == 404


class TestCategoriesEndpoints:
    def test_create_and_list(self, client):
        r = client.post("/api/categories", json={"name": "supermercado", "color": "#ff0000"})
        assert r.status_code == 200
        r2 = client.get("/api/categories")
        assert len(r2.json()) == 1

    def test_duplicate_category_returns_error(self, client):
        client.post("/api/categories", json={"name": "food"})
        r = client.post("/api/categories", json={"name": "food"})
        # The category endpoint converts both ValueError and IntegrityError to 400
        assert r.status_code in (400, 409)

    def test_update_category(self, client):
        cat = client.post("/api/categories", json={"name": "vieja"}).json()
        r = client.patch(f"/api/categories/{cat['id']}", json={"name": "nueva"})
        assert r.status_code == 200
        assert r.json()["name"] == "nueva"

    def test_delete_category(self, client):
        cat = client.post("/api/categories", json={"name": "temporal"}).json()
        r = client.delete(f"/api/categories/{cat['id']}")
        assert r.status_code == 204


class TestFxRatesEndpoints:
    def test_create_fx_rate(self, client):
        r = client.post(
            "/api/fx",
            json={"year_month": "2025-01", "currency": "USD", "rate_to_ars": 1200.0},
        )
        assert r.status_code == 200
        assert r.json()["rate_to_ars"] == 1200.0

    def test_upsert_fx_rate(self, client):
        client.post("/api/fx", json={"year_month": "2025-01", "currency": "USD", "rate_to_ars": 1200.0})
        r = client.post("/api/fx", json={"year_month": "2025-01", "currency": "USD", "rate_to_ars": 1300.0})
        assert r.status_code == 200
        assert r.json()["rate_to_ars"] == 1300.0
        r2 = client.get("/api/fx")
        assert len(r2.json()) == 1


class TestMonthBreakdownEndpoint:
    def test_month_breakdown(self, client):
        person = client.post("/api/people", json={"name": "Alice"}).json()
        card = client.post(
            "/api/cards",
            json={"name": "Visa", "provider": "visa", "owner_person_id": person["id"]},
        ).json()
        client.post(
            "/api/purchases",
            json={
                "card_id": card["id"],
                "purchase_date": "2025-01-15",
                "description": "Groceries",
                "currency": "ARS",
                "amount_original": 50000,
            },
        )
        r = client.get("/api/reports/month-breakdown?year_month=2025-01")
        assert r.status_code == 200
        data = r.json()
        assert data["year_month"] == "2025-01"
        assert data["total_ars"] == 50000.0
        assert len(data["items"]) == 1
