# -*- coding: utf-8 -*-
# Raksha — Entity Extraction Validation Tests

from backend.app.intel.campaigns import extract_entities_regex

def test_extract_phone_numbers():
    text = "Call me at +91-9876543210 or 9876543210 immediately."
    entities = extract_entities_regex(text)
    
    phones = [e["value"] for e in entities if e["type"] == "phone"]
    assert "+91-9876543210" in phones or "9876543210" in phones
    assert len(phones) >= 1

def test_extract_upi_ids():
    text = "Transfer money to officer.verma@okaxis or scammer123@ybl now."
    entities = extract_entities_regex(text)
    
    upis = [e["value"] for e in entities if e["type"] == "upi"]
    assert "officer.verma@okaxis" in upis
    assert "scammer123@ybl" in upis
    assert len(upis) == 2

def test_extract_bank_accounts():
    text = "Deposit verification amount to Account: 123456789012 (IFS code HDFC00001)."
    entities = extract_entities_regex(text)
    
    accounts = [e["value"] for e in entities if e["type"] == "account"]
    assert "123456789012" in accounts
    assert len(accounts) == 1

def test_extract_urls():
    text = "Check your package tracking at fedex-customs-verify.in or visit http://dhl-clearance.com/verify."
    entities = extract_entities_regex(text)
    
    urls = [e["value"] for e in entities if e["type"] == "url"]
    assert "fedex-customs-verify.in" in urls
    assert "http://dhl-clearance.com/verify" in urls
    assert len(urls) == 2

def test_extract_agencies():
    text = "This is CBI headquarters Maharashtra Cyber Cell and Supreme Court warning."
    entities = extract_entities_regex(text)
    
    agencies = [e["value"] for e in entities if e["type"] == "agency"]
    assert "CBI" in agencies
    assert "CYBER CELL" in agencies
    assert "SUPREME COURT" in agencies
    assert len(agencies) == 3
