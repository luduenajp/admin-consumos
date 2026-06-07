"""Tests for Beneficiary CRUD and match_beneficiary logic."""
from __future__ import annotations

import pytest

from app.crud import (
    create_beneficiary,
    delete_beneficiary,
    list_beneficiaries,
    match_beneficiary,
    update_beneficiary,
)
from app.schemas import BeneficiaryCreate, BeneficiaryUpdate


class TestBeneficiaryCRUD:
    def test_create_and_list(self, session):
        b = create_beneficiary(session=session, payload=BeneficiaryCreate(name="Verdulería Lopez"))
        assert b.id is not None
        assert b.name == "Verdulería Lopez"
        assert b.cbu is None

        bs = list_beneficiaries(session=session)
        assert len(bs) == 1
        assert bs[0].name == "Verdulería Lopez"

    def test_create_with_all_fields(self, session):
        b = create_beneficiary(
            session=session,
            payload=BeneficiaryCreate(name="Kiosco", cbu="123456789012345678901", cuit="20-12345678-9", alias="kiosco.pago")
        )
        assert b.cbu == "123456789012345678901"
        assert b.cuit == "20-12345678-9"
        assert b.alias == "kiosco.pago"

    def test_update_partial(self, session):
        b = create_beneficiary(session=session, payload=BeneficiaryCreate(name="Farmacia"))
        updated = update_beneficiary(session=session, beneficiary_id=b.id, payload=BeneficiaryUpdate(cbu="987654321"))
        assert updated.name == "Farmacia"
        assert updated.cbu == "987654321"

    def test_update_not_found(self, session):
        with pytest.raises(ValueError, match="not found"):
            update_beneficiary(session=session, beneficiary_id=9999, payload=BeneficiaryUpdate(name="X"))

    def test_delete(self, session):
        b = create_beneficiary(session=session, payload=BeneficiaryCreate(name="Panadería"))
        delete_beneficiary(session=session, beneficiary_id=b.id)
        assert list_beneficiaries(session=session) == []

    def test_delete_not_found(self, session):
        with pytest.raises(ValueError, match="not found"):
            delete_beneficiary(session=session, beneficiary_id=9999)

    def test_list_ordered_by_name(self, session):
        create_beneficiary(session=session, payload=BeneficiaryCreate(name="Zapatería"))
        create_beneficiary(session=session, payload=BeneficiaryCreate(name="Almacén"))
        bs = list_beneficiaries(session=session)
        assert bs[0].name == "Almacén"
        assert bs[1].name == "Zapatería"


class TestMatchBeneficiary:
    def test_no_match_empty_table(self, session):
        result = match_beneficiary(session=session, name="Nadie", cbu=None, cuit=None, alias=None)
        assert result is None

    def test_exact_cbu_match(self, session):
        b = create_beneficiary(
            session=session,
            payload=BeneficiaryCreate(name="Verdulería", cbu="1234567890123456789012")
        )
        result = match_beneficiary(session=session, name=None, cbu="1234567890123456789012", cuit=None, alias=None)
        assert result is not None
        matched, confidence = result
        assert matched.id == b.id
        assert confidence == "exact"

    def test_exact_cuit_match(self, session):
        b = create_beneficiary(
            session=session,
            payload=BeneficiaryCreate(name="Empresa", cuit="20-12345678-9")
        )
        result = match_beneficiary(session=session, name=None, cbu=None, cuit="20-12345678-9", alias=None)
        assert result is not None
        _, confidence = result
        assert confidence == "exact"

    def test_fuzzy_alias_match(self, session):
        b = create_beneficiary(
            session=session,
            payload=BeneficiaryCreate(name="Kiosco", alias="kiosco.pago")
        )
        # Alias with different casing/spaces normalizes to same
        result = match_beneficiary(session=session, name=None, cbu=None, cuit=None, alias="KIOSCO.PAGO")
        assert result is not None
        matched, confidence = result
        assert matched.id == b.id
        assert confidence == "fuzzy"

    def test_fuzzy_name_match(self, session):
        b = create_beneficiary(session=session, payload=BeneficiaryCreate(name="Verdulería Lopez"))
        # Similar name should match with >= 80% similarity
        result = match_beneficiary(session=session, name="VERDULERIA LOPEZ", cbu=None, cuit=None, alias=None)
        assert result is not None
        _, confidence = result
        assert confidence == "fuzzy"

    def test_no_match_low_similarity(self, session):
        create_beneficiary(session=session, payload=BeneficiaryCreate(name="Verdulería Lopez"))
        result = match_beneficiary(session=session, name="Zapatería Jones", cbu=None, cuit=None, alias=None)
        assert result is None

    def test_exact_takes_priority_over_fuzzy(self, session):
        b_exact = create_beneficiary(
            session=session,
            payload=BeneficiaryCreate(name="Lopez Maria", cbu="111")
        )
        create_beneficiary(
            session=session,
            payload=BeneficiaryCreate(name="Lopez Mario")
        )
        result = match_beneficiary(session=session, name="Lopez Mario", cbu="111", cuit=None, alias=None)
        assert result is not None
        matched, confidence = result
        assert matched.id == b_exact.id
        assert confidence == "exact"
