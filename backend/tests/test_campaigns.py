# -*- coding: utf-8 -*-
# Raksha — Campaign Clustering Validation Tests

import pytest
from pathlib import Path
from backend.app.store import AuditStore
from backend.app.intel.campaigns import compute_campaign_clusters

def test_campaign_clustering_shared_infrastructure(tmp_path, monkeypatch):
    # Initialize clean store
    test_store = AuditStore(db_path=tmp_path / "campaign_test.db")
    
    # Mock get_store to return our temporary test store
    import backend.app.intel.campaigns
    monkeypatch.setattr(backend.app.intel.campaigns, "get_store", lambda: test_store)

    # 1. Log two cases sharing a phone number (+91-9876500001)
    test_store.log_case(
        case_id="case-a",
        input_text="Your Aadhaar is linked to a money laundering case. CBI Officer. Call +91-9876500001.",
        language="en",
        label="SCAM",
        scam_type="digital_arrest",
        confidence=0.9,
        reasons="CBI scam",
        signals=["impersonation"],
        model_used="test",
        full_response={}
    )

    test_store.log_case(
        case_id="case-b",
        input_text="FedEx parcel seized. Mumbai customs narcotics division. Call +91-9876500001.",
        language="en",
        label="SCAM",
        scam_type="courier_parcel",
        confidence=0.92,
        reasons="FedEx scam",
        signals=["impersonation"],
        model_used="test",
        full_response={}
    )

    # 2. Log a third case that shares nothing (safe transaction alert)
    test_store.log_case(
        case_id="case-c",
        input_text="Your OTP for login is 123456. Swiggy.",
        language="en",
        label="SAFE",
        scam_type=None,
        confidence=0.99,
        reasons="Swiggy OTP",
        signals=[],
        model_used="test",
        full_response={}
    )

    # Compute clusters
    campaigns = compute_campaign_clusters()
    
    # We should have exactly 1 campaign containing case-a and case-b
    assert len(campaigns) == 1
    camp = campaigns[0]
    assert len(camp["case_ids"]) == 2
    assert "case-a" in camp["case_ids"]
    assert "case-b" in camp["case_ids"]
    assert "case-c" not in camp["case_ids"]
    
    # Check that the shared phone is in campaign entities
    phones = [e["value"] for e in camp["entities"] if e["type"] == "phone"]
    assert "9876500001" in phones
