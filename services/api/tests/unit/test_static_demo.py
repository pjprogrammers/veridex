"""Unit tests for the static demo response layer (SIH prototype)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from app.static_demo import (
    AADHAAR_IMAGE_HASH,
    STATIC_SCENARIOS,
    canonical_result_hash,
    known_scenario,
    scenario_for_document,
    static_forensics,
    static_mrz,
    static_verification,
)


class _FakeDB:
    def __init__(self, case=None):
        self._case = case

    async def get(self, model, pk):
        return self._case


class _FakeCase:
    def __init__(self, scenario=None):
        self.case_metadata = {"scenario": scenario} if scenario else {}


class _FakeDoc:
    def __init__(self, case_id=None, content_hash=""):
        self.case_id = case_id
        self.content_hash = content_hash


@pytest.mark.anyio
async def test_unknown_scenario_returns_none():
    assert known_scenario("does_not_exist") is None
    assert known_scenario("") is None
    assert known_scenario(None) is None


@pytest.mark.anyio
async def test_no_scenario_runs_real_pipeline():
    db = _FakeDB(case=_FakeCase(scenario=None))
    doc = _FakeDoc(case_id="case-1", content_hash="deadbeef")
    assert await scenario_for_document(db, doc) is None


@pytest.mark.anyio
async def test_case_scenario_takes_priority():
    db = _FakeDB(case=_FakeCase(scenario="anil"))
    doc = _FakeDoc(case_id="case-1", content_hash="ignored-hash")
    assert await scenario_for_document(db, doc) == "anil"


@pytest.mark.anyio
async def test_invalid_case_scenario_ignored():
    db = _FakeDB(case=_FakeCase(scenario="bogus"))
    doc = _FakeDoc(case_id="case-1", content_hash=AADHAAR_IMAGE_HASH)
    assert await scenario_for_document(db, doc) == "aadhaar"


@pytest.mark.anyio
async def test_piyush_aadhaar_hash_resolves():
    db = _FakeDB()
    doc = _FakeDoc(case_id=None, content_hash=AADHAAR_IMAGE_HASH)
    assert await scenario_for_document(db, doc) == "aadhaar"


@pytest.mark.anyio
async def test_all_scenarios_known():
    for key in STATIC_SCENARIOS:
        assert known_scenario(key) is not None


@pytest.mark.anyio
async def test_verification_outcomes_match_sample_cases():
    assert static_verification(known_scenario("suresh"), "d1")["risk"]["level"] == "LOW"
    assert static_verification(known_scenario("priya"), "d1")["risk"]["level"] == "LOW"
    assert static_verification(known_scenario("rajesh"), "d1")["risk"]["level"] == "HIGH"
    assert static_verification(known_scenario("neha"), "d1")["risk"]["level"] == "HIGH"
    assert static_verification(known_scenario("anil"), "d1")["risk"]["level"] == "HIGH"
    assert static_verification(known_scenario("amit"), "d1")["risk"]["level"] == "MEDIUM"
    assert static_verification(known_scenario("rohit"), "d1")["risk"]["level"] == "MEDIUM"
    assert static_verification(known_scenario("kavita"), "d1")["risk"]["level"] == "MEDIUM"
    assert (
        static_verification(known_scenario("aadhaar"), "d1")["risk"]["level"] == "LOW"
    )


@pytest.mark.anyio
async def test_aadhaar_response_fields():
    result = static_verification(known_scenario("aadhaar"), "d1")
    assert result["document_type"] == "aadhaar"
    fields = result["extracted_fields"]
    assert fields["full_name"] == "पीयूष वर्मा"
    assert fields["document_number"] == "5457 0950 4811"
    assert fields["cid/VID"] == "9103 2996 4131 2258"
    assert fields["date_of_birth"] == "18/12/2007"
    assert result["mrz"]["mrz_detected"] is False
    assert result["demo"] is True


@pytest.mark.anyio
async def test_passport_mrz_present_and_valid():
    result = static_verification(known_scenario("suresh"), "d1")
    assert result["document_type"] == "passport"
    assert result["mrz"]["mrz_valid"] is True
    assert len(result["mrz"]["raw_mrz"]) == 2


@pytest.mark.anyio
async def test_neha_mrz_mismatch_flags():
    result = static_verification(known_scenario("neha"), "d1")
    assert result["mrz"]["mrz_valid"] is False
    assert result["cross_validation"]["overall"] == "FAIL"


@pytest.mark.anyio
async def test_static_mrz_and_forensics_payloads():
    scenario = known_scenario("anil")
    mrz = static_mrz(scenario, "d1")
    assert mrz["document_id"] == "d1"
    assert len(mrz["mrz"]["raw_mrz"]) == 2 or mrz["comparison"] is not None
    forensics = static_forensics(scenario, "d1")
    assert forensics["level"] == "HIGH"
    assert forensics["tampering_score"] == 0.81
    assert forensics["document_id"] == "d1"


@pytest.mark.anyio
async def test_canonical_result_hash_is_deterministic_and_sensitive():
    result = static_verification(known_scenario("aadhaar"), "d1")
    first = canonical_result_hash(result)
    assert len(first) == 64
    assert first == canonical_result_hash(dict(result))

    tampered = dict(result)
    tampered["risk"] = {**result["risk"], "score": 0.99}
    assert canonical_result_hash(tampered) != first
