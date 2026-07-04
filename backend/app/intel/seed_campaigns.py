# -*- coding: utf-8 -*-
# Raksha — Campaign Seeder Script
# Seeds 18 cases forming 3 campaigns to show in the Campaign Intel graph.

import os
import sys
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.store import get_store

# Synthetic Cases data
CAMPAIGN_CASES = [
    # Campaign A: Digital Arrest (CBI Officer Sharma, UPI: officer.sharma@ybl, Phone: +91-9876500001)
    {
        "input_text": "Your Aadhaar is linked to a money laundering case in Mumbai. This is Officer Sharma from CBI. You are under digital arrest. Call +91-9876500001 immediately. Pay via UPI officer.sharma@ybl to clear your name.",
        "label": "SCAM",
        "scam_type": "digital_arrest",
        "confidence": 0.95,
        "reasons": "CBI Officer Sharma impersonation demanding money under threat of digital arrest.",
        "signals": ["authority impersonation", "demand money", "threat of arrest", "urgency"],
        "hours_offset": -24
    },
    {
        "input_text": "Alert from TRAI. Your SIM card is flagged for sending illegal advertisements. Transferring you to CBI Officer Sharma. Do not hang up the video call. Contact +91-9876500001 or pay verification fee to officer.sharma@ybl.",
        "label": "SCAM",
        "scam_type": "digital_arrest",
        "confidence": 0.92,
        "reasons": "TRAI deactivation threat routed to fake CBI Officer Sharma, demanding verification fee.",
        "signals": ["authority impersonation", "threat of SIM deactivation", "demand money", "video call coercion"],
        "hours_offset": -22
    },
    {
        "input_text": "This is Customs Department. A package containing illegal drugs was sent using your credentials. Please speak to CBI Officer Sharma at +91-9876500001. You must transfer funds to officer.sharma@ybl immediately.",
        "label": "SCAM",
        "scam_type": "digital_arrest",
        "confidence": 0.96,
        "reasons": "Customs parcel seizure fake routing to CBI Officer Sharma with immediate payment demand.",
        "signals": ["authority impersonation", "illegal parcel claim", "demand money", "urgency"],
        "hours_offset": -20
    },
    {
        "input_text": "Mumbai Police cyber cell alert: Warrant issued under your name for suspicious money transfers. Under digital arrest. Stay on camera. Verify via UPI officer.sharma@ybl. Contact support at +91-9876500001.",
        "label": "SCAM",
        "scam_type": "digital_arrest",
        "confidence": 0.94,
        "reasons": "Cyber cell impersonation demanding UPI verification under video call digital arrest coercion.",
        "signals": ["authority impersonation", "threat of arrest", "demand money", "video call coercion"],
        "hours_offset": -18
    },
    {
        "input_text": "CBI investigation notice: Money laundering found in your bank accounts. Officer Sharma demands instant verification payment to officer.sharma@ybl to avoid locking assets. Emergency helpline: +91-9876500001.",
        "label": "SCAM",
        "scam_type": "digital_arrest",
        "confidence": 0.91,
        "reasons": "Money laundering investigation threat demanding immediate asset verification deposit.",
        "signals": ["authority impersonation", "asset blocking threat", "demand money", "urgency"],
        "hours_offset": -16
    },
    {
        "input_text": "CBI Officer Sharma calls regarding a parcel containing fake passports and illegal items under your name. Pay officer.sharma@ybl or face immediate arrest. Phone: +91-9876500001.",
        "label": "SCAM",
        "scam_type": "digital_arrest",
        "confidence": 0.95,
        "reasons": "Fake passport parcel seizure threat demanding immediate payment to clear name.",
        "signals": ["authority impersonation", "illegal parcel claim", "demand money", "threat of arrest"],
        "hours_offset": -14
    },

    # Campaign B: Courier Parcel (FedEx Customs Seizure, URL: fedex-customs-verify.in, Phone: +91-8765400002)
    {
        "input_text": "Your FedEx shipment is detained by customs due to contraband items. Call +91-8765400002 or verify online at fedex-customs-verify.in to avoid legal charges.",
        "label": "SCAM",
        "scam_type": "courier_parcel",
        "confidence": 0.90,
        "reasons": "FedEx parcel seizure threat directing to lookalike verification link.",
        "signals": ["brand impersonation", "illegal parcel claim", "lookalike link", "urgency"],
        "hours_offset": -12
    },
    {
        "input_text": "DHL alert: Illegal chemicals found in your outbound parcel. Route to Customs department. Log on to fedex-customs-verify.in or call +91-8765400002 to resolve.",
        "label": "SCAM",
        "scam_type": "courier_parcel",
        "confidence": 0.88,
        "reasons": "DHL shipment seizure threat directed to a lookalike fedex verification link.",
        "signals": ["brand impersonation", "illegal parcel claim", "lookalike link", "threat of customs arrest"],
        "hours_offset": -11
    },
    {
        "input_text": "Customs officer claims your FedEx parcel to Taiwan is intercepted with fake passports. Visit fedex-customs-verify.in to submit KYC or call +91-8765400002.",
        "label": "SCAM",
        "scam_type": "courier_parcel",
        "confidence": 0.93,
        "reasons": "Customs impersonation alleging passport smuggling, directing to phishing KYC site.",
        "signals": ["authority impersonation", "illegal parcel claim", "lookalike link", "urgency"],
        "hours_offset": -10
    },
    {
        "input_text": "Urgent Blue Dart parcel update: Cargo seized containing contrabands. Verify details with agent at +91-8765400002 or visit fedex-customs-verify.in for online clearance.",
        "label": "SCAM",
        "scam_type": "courier_parcel",
        "confidence": 0.87,
        "reasons": "Blue Dart seizure spoofing directing user to lookalike clearance website.",
        "signals": ["brand impersonation", "illegal parcel claim", "lookalike link", "urgency"],
        "hours_offset": -9
    },
    {
        "input_text": "Package from Mumbai containing illegal drugs linked to your Aadhaar. Call FedEx desk +91-8765400002 or inspect details at fedex-customs-verify.in.",
        "label": "SCAM",
        "scam_type": "courier_parcel",
        "confidence": 0.91,
        "reasons": "FedEx impersonation linking user's Aadhaar to illegal drug shipment.",
        "signals": ["brand impersonation", "illegal parcel claim", "lookalike link", "Aadhaar threat"],
        "hours_offset": -8
    },
    {
        "input_text": "FedEx customs duty pending on imported items. Avoid arrest by submitting verification at fedex-customs-verify.in. Helpline: +91-8765400002.",
        "label": "SCAM",
        "scam_type": "courier_parcel",
        "confidence": 0.89,
        "reasons": "Customs duty verification demand directing to phishing site under threat of arrest.",
        "signals": ["brand impersonation", "demand money", "lookalike link", "threat of arrest"],
        "hours_offset": -7
    },

    # Campaign C: KYC Bank Block (UPI: kycupdate@paytm, Phone: +91-7654300003)
    {
        "input_text": "Dear Customer, your SBI account is blocked. Update your KYC details now by transferring a token amount via UPI to kycupdate@paytm. Helpline: +91-7654300003.",
        "label": "SCAM",
        "scam_type": "kyc_bank",
        "confidence": 0.91,
        "reasons": "SBI account blocking threat demanding UPI KYC verification deposit.",
        "signals": ["brand impersonation", "account blocking threat", "demand money", "UPI request"],
        "hours_offset": -6
    },
    {
        "input_text": "Urgent PNB alert: PAN details expired. Link to prevent account suspension. Pay verification deposit via UPI kycupdate@paytm or call +91-7654300003.",
        "label": "SCAM",
        "scam_type": "kyc_bank",
        "confidence": 0.89,
        "reasons": "PAN expiry suspension threat demanding UPI verification deposit.",
        "signals": ["brand impersonation", "account suspension threat", "demand money", "UPI request"],
        "hours_offset": -5
    },
    {
        "input_text": "Your HDFC Credit Card has been suspended due to pending KYC. To unblock, send a verification deposit via UPI to kycupdate@paytm. Contact +91-7654300003.",
        "label": "SCAM",
        "scam_type": "kyc_bank",
        "confidence": 0.90,
        "reasons": "Credit card suspension threat demanding UPI KYC verification.",
        "signals": ["brand impersonation", "card suspension threat", "demand money", "UPI request"],
        "hours_offset": -4
    },
    {
        "input_text": "TRAI notice: Your mobile number will be deactivated within 2 hours. Submit Aadhaar KYC. Contact +91-7654300003 or make UPI payment to kycupdate@paytm.",
        "label": "SCAM",
        "scam_type": "kyc_bank",
        "confidence": 0.92,
        "reasons": "TRAI number deactivation threat demanding UPI verification deposit.",
        "signals": ["authority impersonation", "threat of SIM deactivation", "demand money", "UPI request"],
        "hours_offset": -3
    },
    {
        "input_text": "KYC update required for your Paytm wallet to keep transaction limits. Complete verification via UPI deposit to kycupdate@paytm. Inquiries at +91-7654300003.",
        "label": "SCAM",
        "scam_type": "kyc_bank",
        "confidence": 0.86,
        "reasons": "Paytm wallet KYC update demanding verification deposit.",
        "signals": ["brand impersonation", "demand money", "UPI request", "urgency"],
        "hours_offset": -2
    },
    {
        "input_text": "Dear User, your bank KYC verification is overdue. Dial +91-7654300003 or complete KYC instantly by depositing via UPI to kycupdate@paytm.",
        "label": "SCAM",
        "scam_type": "kyc_bank",
        "confidence": 0.87,
        "reasons": "Overdue bank KYC alert demanding instant UPI deposit.",
        "signals": ["brand impersonation", "demand money", "UPI request", "urgency"],
        "hours_offset": -1
    }
]

def seed_cases():
    """Seeds the synthetic cases to seed campaigns."""
    store = get_store()
    
    # Check if we already have these seeded
    existing_count = store.count_cases()
    if existing_count >= 18:
        print(f"Database already contains {existing_count} cases. Skipping seed script.")
        return

    print(f"Seeding {len(CAMPAIGN_CASES)} synthetic campaign cases...")
    base_time = datetime.now(timezone.utc)
    
    from uuid import uuid4
    
    for case in CAMPAIGN_CASES:
        case_id = f"demo-{uuid4().hex[:12]}"
        timestamp = base_time + timedelta(hours=case["hours_offset"])
        
        # Build empty responses
        full_resp = {
            "case_id": case_id,
            "language": "en",
            "verdict": case["label"],
            "reply_text": "🚫 SCAM DETECTED\n\n" + case["reasons"],
            "classification": {
                "label": case["label"],
                "scam_type": case["scam_type"],
                "confidence": case["confidence"],
                "signals": case["signals"],
                "reasons": case["reasons"]
            }
        }
        
        store.log_case(
            case_id=case_id,
            input_text=case["input_text"],
            language="en",
            label=case["label"],
            scam_type=case["scam_type"],
            confidence=case["confidence"],
            reasons=case["reasons"],
            signals=case["signals"],
            model_used="seeded-demo-model",
            full_response=full_resp,
            guidance_json=None,
            complaint_json=None,
            alert_json=None
        )
    
    # Force run entity extraction immediately
    from backend.app.intel.campaigns import run_entity_extraction
    import asyncio
    asyncio.run(run_entity_extraction())
    
    print("Seed complete successfully!")

if __name__ == "__main__":
    seed_cases()
