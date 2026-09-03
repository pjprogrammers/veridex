"""Tests for the tamper-evident audit trail."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))



from app.models.models import VerificationCase
from app.services.audit import append_audit_entry, compute_entry_hash, verify_chain


async def _make_case(db) -> VerificationCase:
    case = VerificationCase(
        case_number="TEST-0001",
        description="test case",
    )
    db.add(case)
    await db.flush()
    return case


async def test_append_first_entry_has_no_previous_hash(db_session):
    case = await _make_case(db_session)
    entry = await append_audit_entry(
        db_session,
        case_id=case.id,
        action="case_created",
        actor_id=None,
        actor_role="officer",
        payload={"note": "test"},
    )
    assert entry.previous_hash is None
    assert entry.current_hash
    assert len(entry.current_hash) == 64  # SHA-256 hex


async def test_chain_linking(db_session):
    case = await _make_case(db_session)
    e1 = await append_audit_entry(
        db_session, case_id=case.id, action="action_one", actor_id=None, actor_role="officer"
    )
    e2 = await append_audit_entry(
        db_session, case_id=case.id, action="action_two", actor_id=None, actor_role="officer"
    )
    assert e2.previous_hash == e1.current_hash


async def test_verify_chain_valid(db_session):
    case = await _make_case(db_session)
    for action in ("create", "update", "verify", "close"):
        await append_audit_entry(
            db_session, case_id=case.id, action=action, actor_id=None, actor_role="officer"
        )
    result = await verify_chain(db_session, case.id)
    assert result["valid"] is True
    assert result["total_entries"] == 4
    assert result["integrity_issues"] == []


async def test_verify_chain_detects_tamper(db_session):
    case = await _make_case(db_session)
    e1 = await append_audit_entry(
        db_session, case_id=case.id, action="action_one", actor_id=None, actor_role="officer"
    )
    await append_audit_entry(
        db_session, case_id=case.id, action="action_two", actor_id=None, actor_role="officer"
    )

    # Simulate tampering: change the payload of entry 1
    e1.payload = {"note": "tampered"}  # type: ignore[assignment]
    await db_session.flush()

    result = await verify_chain(db_session, case.id)
    assert result["valid"] is False
    assert any(i["reason"] == "hash_mismatch" for i in result["integrity_issues"])


async def test_verify_chain_detects_broken_link(db_session):
    case = await _make_case(db_session)
    e1 = await append_audit_entry(
        db_session, case_id=case.id, action="action_one", actor_id=None, actor_role="officer"
    )
    await append_audit_entry(
        db_session, case_id=case.id, action="action_two", actor_id=None, actor_role="officer"
    )

    # Break the chain: rewrite e1's current hash
    e1.current_hash = "0" * 64  # type: ignore[assignment]
    await db_session.flush()

    result = await verify_chain(db_session, case.id)
    assert result["valid"] is False
    reasons = [i["reason"] for i in result["integrity_issues"]]
    assert "hash_mismatch" in reasons or "broken_chain" in reasons


async def test_compute_hash_is_deterministic():
    args = dict(
        entry_id=1,
        case_id="case-1",
        action="test",
        actor_id="actor-1",
        actor_role="officer",
        timestamp="2026-01-01T00:00:00",
        previous_hash=None,
        payload={"a": 1},
    )
    h1 = compute_entry_hash(**args)
    h2 = compute_entry_hash(**args)
    assert h1 == h2
    assert len(h1) == 64


async def test_compute_hash_changes_with_payload():
    base = dict(
        entry_id=1,
        case_id="case-1",
        action="test",
        actor_id="actor-1",
        actor_role="officer",
        timestamp="2026-01-01T00:00:00",
        previous_hash=None,
        payload={"a": 1},
    )
    h1 = compute_entry_hash(**base)
    h2 = compute_entry_hash(**{**base, "payload": {"a": 2}})
    assert h1 != h2
