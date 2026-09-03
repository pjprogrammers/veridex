"""Integration tests for registry service."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from app.services import registry as registry_service


async def test_create_and_lookup(db_session):
    await registry_service.create_entry(
        db_session,
        registry_type="passport",
        document_number="AB123456X",
        status="valid",
        holder_name="Jordan Smith",
        issuing_country="GB",
    )
    await db_session.commit()

    entries = await registry_service.lookup(db_session, "AB123456X")
    assert len(entries) == 1
    assert entries[0].status == "valid"
    assert entries[0].holder_name == "Jordan Smith"


async def test_lookup_not_found(db_session):
    entries = await registry_service.lookup(db_session, "ZZ999999")
    assert entries == []


async def test_lookup_filtered_by_type(db_session):
    await registry_service.create_entry(
        db_session, registry_type="passport", document_number="CD123456"
    )
    await registry_service.create_entry(
        db_session, registry_type="national_id", document_number="EF123456"
    )
    await db_session.commit()

    passport = await registry_service.lookup(db_session, "CD123456", "passport")
    assert len(passport) == 1

    # Wrong type won't match
    wrong = await registry_service.lookup(db_session, "CD123456", "national_id")
    assert wrong == []


async def test_invalid_type_rejected(db_session):
    with pytest.raises(ValueError):
        await registry_service.create_entry(
            db_session, registry_type="criminal_record", document_number="GH123456"
        )


async def test_invalid_status_rejected(db_session):
    with pytest.raises(ValueError):
        await registry_service.create_entry(
            db_session,
            registry_type="passport",
            document_number="IJ123456",
            status="deceased",
        )


async def test_list_entries_with_filter(db_session):
    await registry_service.create_entry(
        db_session, registry_type="passport", document_number="KL123456", status="valid"
    )
    await registry_service.create_entry(
        db_session,
        registry_type="passport",
        document_number="MN123456",
        status="reported_stolen",
    )
    await db_session.commit()

    entries, total = await registry_service.list_entries(
        db_session, limit=10, offset=0, status_filter="reported_stolen"
    )
    assert total == 1
    assert entries[0].document_number == "MN123456"
