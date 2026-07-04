# -*- coding: utf-8 -*-
# Raksha — Hash Chain Audit Verification Tests

import pytest
from pathlib import Path
from backend.app.store import AuditStore, _compute_record_hash, CaseRecord

def test_hash_chain_integrity(tmp_path):
    # Initialize a clean test store in a temporary directory
    store = AuditStore(db_path=tmp_path / "audit_test.db")

    # 1. Log genesis case
    store.log_case(
        case_id="case-001",
        input_text="Suspicious CBI message",
        language="en",
        label="SCAM",
        scam_type="digital_arrest",
        confidence=0.95,
        reasons="CBI officer scam",
        signals=["authority impersonation", "urgency"],
        model_used="test-model",
        full_response={"verdict": "SCAM"}
    )

    # 2. Log subsequent cases
    store.log_case(
        case_id="case-002",
        input_text="Legitimate Swiggy order",
        language="en",
        label="SAFE",
        scam_type=None,
        confidence=0.99,
        reasons="Swiggy delivery confirmation",
        signals=[],
        model_used="test-model",
        full_response={"verdict": "SAFE"}
    )

    store.log_case(
        case_id="case-003",
        input_text="SBI OTP code: 123456",
        language="en",
        label="SAFE",
        scam_type=None,
        confidence=0.98,
        reasons="SBI OTP transaction",
        signals=[],
        model_used="test-model",
        full_response={"verdict": "SAFE"}
    )

    # Verify the chain is intact
    report = store.verify_chain()
    assert report["intact"] is True
    assert report["total_records"] == 3
    assert report["verified_records"] == 3
    assert report["first_broken_record"] is None

    # Retrieve case 2 to verify hashes are present and linked
    case1 = store.get_case("case-001")
    case2 = store.get_case("case-002")
    case3 = store.get_case("case-003")

    assert case1.prev_hash is None
    assert case1.record_hash is not None
    assert case2.prev_hash == case1.record_hash
    assert case3.prev_hash == case2.record_hash

    # 3. Simulate tampering: modify the content of case 2 directly in the database session
    session = store._get_session()
    record = session.query(CaseRecord).filter_by(case_id="case-002").first()
    # Tamper with the label/text
    record.label = "SCAM"
    session.commit()
    session.close()

    # Re-verify the chain -> should be broken!
    tampered_report = store.verify_chain()
    assert tampered_report["intact"] is False
    assert tampered_report["first_broken_record"] == "case-002"
    assert "mismatch" in tampered_report["error"] or "broken" in tampered_report["error"]
