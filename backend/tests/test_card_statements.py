"""Tests for CardStatement CRUD and suggest-month logic."""
from datetime import date

import pytest

from app.schemas import CardStatementCreate, SuggestMonthResponse


class TestCardStatementSchemas:
    def test_valid_schema(self):
        cs = CardStatementCreate(
            card_id=1,
            year_month="2026-04",
            closing_date=date(2026, 4, 6),
            due_date=date(2026, 4, 28),
        )
        assert cs.card_id == 1
        assert cs.year_month == "2026-04"

    def test_invalid_year_month_format(self):
        with pytest.raises(Exception):
            CardStatementCreate(
                card_id=1,
                year_month="04-2026",  # wrong format
                closing_date=date(2026, 4, 6),
            )

    def test_due_date_optional(self):
        cs = CardStatementCreate(
            card_id=1,
            year_month="2026-04",
            closing_date=date(2026, 4, 6),
        )
        assert cs.due_date is None

    def test_suggest_month_response(self):
        r = SuggestMonthResponse(year_month="2026-04", closing_date=date(2026, 4, 6), fallback=False)
        assert r.year_month == "2026-04"
        assert r.fallback is False

    def test_suggest_month_fallback_has_no_closing_date(self):
        r = SuggestMonthResponse(year_month="2026-05", closing_date=None, fallback=True)
        assert r.closing_date is None


from app.crud import (
    delete_card_statement,
    list_card_statements,
    suggest_first_installment_month,
    upsert_card_statement,
)
from app.models import CardStatement
from app.schemas import CardStatementCreate


class TestCardStatementCRUD:
    def test_upsert_creates_new(self, session, two_person_scenario):
        s = two_person_scenario
        cs = upsert_card_statement(
            session=session,
            payload=CardStatementCreate(
                card_id=s["alice_card"].id,
                year_month="2026-04",
                closing_date=date(2026, 4, 6),
                due_date=date(2026, 4, 28),
            ),
        )
        assert cs.id is not None
        assert cs.closing_date == date(2026, 4, 6)

    def test_upsert_updates_existing(self, session, two_person_scenario):
        s = two_person_scenario
        payload = CardStatementCreate(
            card_id=s["alice_card"].id,
            year_month="2026-04",
            closing_date=date(2026, 4, 6),
        )
        upsert_card_statement(session=session, payload=payload)
        updated = upsert_card_statement(
            session=session,
            payload=CardStatementCreate(
                card_id=s["alice_card"].id,
                year_month="2026-04",
                closing_date=date(2026, 4, 8),
                due_date=date(2026, 4, 30),
            ),
        )
        assert updated.closing_date == date(2026, 4, 8)
        records = list_card_statements(session=session, card_id=s["alice_card"].id)
        assert len(records) == 1

    def test_list_card_statements_ordered(self, session, two_person_scenario):
        s = two_person_scenario
        upsert_card_statement(session=session, payload=CardStatementCreate(
            card_id=s["alice_card"].id, year_month="2026-05",
            closing_date=date(2026, 5, 8),
        ))
        upsert_card_statement(session=session, payload=CardStatementCreate(
            card_id=s["alice_card"].id, year_month="2026-04",
            closing_date=date(2026, 4, 6),
        ))
        records = list_card_statements(session=session, card_id=s["alice_card"].id)
        assert len(records) == 2
        assert records[0].year_month == "2026-04"
        assert records[1].year_month == "2026-05"

    def test_delete_card_statement(self, session, two_person_scenario):
        s = two_person_scenario
        cs = upsert_card_statement(session=session, payload=CardStatementCreate(
            card_id=s["alice_card"].id, year_month="2026-04",
            closing_date=date(2026, 4, 6),
        ))
        delete_card_statement(session=session, statement_id=cs.id)
        records = list_card_statements(session=session, card_id=s["alice_card"].id)
        assert len(records) == 0

    def test_delete_nonexistent_raises(self, session):
        with pytest.raises(ValueError, match="CardStatement 999 not found"):
            delete_card_statement(session=session, statement_id=999)


class TestSuggestFirstInstallmentMonth:
    def test_purchase_before_closing(self, session, two_person_scenario):
        s = two_person_scenario
        upsert_card_statement(session=session, payload=CardStatementCreate(
            card_id=s["alice_card"].id, year_month="2026-04",
            closing_date=date(2026, 4, 6),
        ))
        ym, closing, fallback = suggest_first_installment_month(
            session=session, card_id=s["alice_card"].id, purchase_date=date(2026, 4, 5)
        )
        assert ym == "2026-04"
        assert closing == date(2026, 4, 6)
        assert fallback is False

    def test_purchase_on_closing_day(self, session, two_person_scenario):
        s = two_person_scenario
        upsert_card_statement(session=session, payload=CardStatementCreate(
            card_id=s["alice_card"].id, year_month="2026-04",
            closing_date=date(2026, 4, 6),
        ))
        ym, closing, fallback = suggest_first_installment_month(
            session=session, card_id=s["alice_card"].id, purchase_date=date(2026, 4, 6)
        )
        assert ym == "2026-04"
        assert fallback is False

    def test_purchase_after_closing_uses_next_statement(self, session, two_person_scenario):
        s = two_person_scenario
        upsert_card_statement(session=session, payload=CardStatementCreate(
            card_id=s["alice_card"].id, year_month="2026-04",
            closing_date=date(2026, 4, 6),
        ))
        upsert_card_statement(session=session, payload=CardStatementCreate(
            card_id=s["alice_card"].id, year_month="2026-05",
            closing_date=date(2026, 5, 8),
        ))
        ym, closing, fallback = suggest_first_installment_month(
            session=session, card_id=s["alice_card"].id, purchase_date=date(2026, 4, 7)
        )
        assert ym == "2026-05"
        assert closing == date(2026, 5, 8)
        assert fallback is False

    def test_no_statement_falls_back_to_next_month(self, session, two_person_scenario):
        s = two_person_scenario
        ym, closing, fallback = suggest_first_installment_month(
            session=session, card_id=s["alice_card"].id, purchase_date=date(2026, 4, 5)
        )
        assert ym == "2026-05"
        assert closing is None
        assert fallback is True

    def test_fallback_wraps_december_to_january(self, session, two_person_scenario):
        s = two_person_scenario
        ym, closing, fallback = suggest_first_installment_month(
            session=session, card_id=s["alice_card"].id, purchase_date=date(2026, 12, 15)
        )
        assert ym == "2027-01"
        assert fallback is True


class TestCardStatementsAPI:
    def test_create_statement(self, client, two_person_scenario):
        s = two_person_scenario
        resp = client.post("/api/card-statements", json={
            "card_id": s["alice_card"].id,
            "year_month": "2026-04",
            "closing_date": "2026-04-06",
            "due_date": "2026-04-28",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["year_month"] == "2026-04"
        assert data["closing_date"] == "2026-04-06"
        assert data["id"] is not None

    def test_upsert_updates_existing(self, client, two_person_scenario):
        s = two_person_scenario
        client.post("/api/card-statements", json={
            "card_id": s["alice_card"].id,
            "year_month": "2026-04",
            "closing_date": "2026-04-06",
        })
        resp = client.post("/api/card-statements", json={
            "card_id": s["alice_card"].id,
            "year_month": "2026-04",
            "closing_date": "2026-04-08",
        })
        assert resp.status_code == 200
        assert resp.json()["closing_date"] == "2026-04-08"

    def test_list_statements(self, client, two_person_scenario):
        s = two_person_scenario
        client.post("/api/card-statements", json={
            "card_id": s["alice_card"].id,
            "year_month": "2026-04",
            "closing_date": "2026-04-06",
        })
        resp = client.get(f"/api/card-statements?card_id={s['alice_card'].id}")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_delete_statement(self, client, two_person_scenario):
        s = two_person_scenario
        create_resp = client.post("/api/card-statements", json={
            "card_id": s["alice_card"].id,
            "year_month": "2026-04",
            "closing_date": "2026-04-06",
        })
        stmt_id = create_resp.json()["id"]
        del_resp = client.delete(f"/api/card-statements/{stmt_id}")
        assert del_resp.status_code == 204
        list_resp = client.get(f"/api/card-statements?card_id={s['alice_card'].id}")
        assert len(list_resp.json()) == 0

    def test_suggest_month_before_closing(self, client, two_person_scenario):
        s = two_person_scenario
        client.post("/api/card-statements", json={
            "card_id": s["alice_card"].id,
            "year_month": "2026-04",
            "closing_date": "2026-04-06",
        })
        resp = client.get(
            f"/api/card-statements/suggest-month"
            f"?card_id={s['alice_card'].id}&purchase_date=2026-04-05"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["year_month"] == "2026-04"
        assert data["fallback"] is False

    def test_suggest_month_fallback(self, client, two_person_scenario):
        s = two_person_scenario
        resp = client.get(
            f"/api/card-statements/suggest-month"
            f"?card_id={s['alice_card'].id}&purchase_date=2026-04-05"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["year_month"] == "2026-05"
        assert data["fallback"] is True
        assert data["closing_date"] is None
