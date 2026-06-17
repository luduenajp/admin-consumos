"""Tests for category CRUD and auto-categorization."""
from datetime import date

import pytest
from sqlmodel import select

from app.crud import (
    auto_categorize_purchases,
    create_category,
    create_purchase,
    delete_category,
    list_categories,
    update_category,
)
from app.models import CurrencyCode, Purchase
from app.schemas import (
    CategoryCreate,
    CategoryUpdate,
    PurchaseCreate,
)


class TestCategoryCRUD:
    def test_create_and_list(self, session):
        cat = create_category(session=session, payload=CategoryCreate(name="supermercado", color="#ff0000"))
        assert cat.id is not None
        assert cat.name == "supermercado"

        categories = list_categories(session=session)
        assert len(categories) == 1

    def test_rename_cascades_to_purchases(self, session, two_person_scenario):
        s = two_person_scenario
        cat = create_category(session=session, payload=CategoryCreate(name="comida"))

        create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 1, 15),
                description="Pizza",
                currency=CurrencyCode.ARS,
                amount_original=5000,
                category="comida",
            ),
        )

        update_category(
            session=session, category_id=cat.id, payload=CategoryUpdate(name="restaurantes")
        )

        purchases = list(session.exec(select(Purchase).where(Purchase.category == "restaurantes")))
        assert len(purchases) == 1
        assert purchases[0].description == "pizza"

        # Old category name should not exist
        old = list(session.exec(select(Purchase).where(Purchase.category == "comida")))
        assert len(old) == 0

    def test_delete_nullifies_purchases(self, session, two_person_scenario):
        s = two_person_scenario
        cat = create_category(session=session, payload=CategoryCreate(name="temporal"))

        create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 1, 15),
                description="Temp purchase",
                currency=CurrencyCode.ARS,
                amount_original=3000,
                category="temporal",
            ),
        )

        delete_category(session=session, category_id=cat.id)

        purchases = list(session.exec(select(Purchase)))
        assert len(purchases) == 1
        assert purchases[0].category is None


class TestAutoCategorizePurchases:
    def test_keyword_categorization(self, session, two_person_scenario):
        s = two_person_scenario
        create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 1, 15),
                description="COTO DIGITAL",
                currency=CurrencyCode.ARS,
                amount_original=15000,
                category=None,
            ),
        )
        create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 1, 16),
                description="NETFLIX",
                currency=CurrencyCode.ARS,
                amount_original=5000,
                category=None,
            ),
        )

        count = auto_categorize_purchases(session=session)
        assert count == 2

        purchases = list(session.exec(select(Purchase).order_by(Purchase.description)))
        categories = {p.description: p.category for p in purchases}
        assert categories["coto digital"] == "Supermercado"
        assert categories["netflix"] == "Servicios"

    def test_already_categorized_not_touched(self, session, two_person_scenario):
        s = two_person_scenario
        create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 1, 15),
                description="COTO ONLINE",
                currency=CurrencyCode.ARS,
                amount_original=10000,
                category="mi-categoria",
            ),
        )
        count = auto_categorize_purchases(session=session)
        assert count == 0

        p = session.exec(select(Purchase)).first()
        assert p.category == "mi-categoria"
