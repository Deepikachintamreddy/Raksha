# -*- coding: utf-8 -*-
# Raksha — Telegram Guardian Alert Unit Tests

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.telegram import TelegramGuardianService

client = TestClient(app)


def test_telegram_message_formatting():
    """Verify that Telegram Guardian alert messages format urgency, signals, and evidence hash correctly."""
    svc = TelegramGuardianService()
    formatted = svc.format_alert_message(
        victim_name="Ramesh Sharma",
        risk_level="HIGH",
        confidence=0.96,
        scam_type="Digital Arrest (CBI / TRAI)",
        observed_signals=["Coercive video call demand", "Fake warrant threat"],
        case_id="CASE-12345",
        record_hash="0xabcd1234ef567890"
    )

    assert "🚨 *GUARDIAN ALERT: DIGITAL ARREST SCAM DETECTED*" in formatted
    assert "👤 *Protected User*: Ramesh Sharma" in formatted
    assert "⚠️ *Risk Level*: *HIGH* (Confidence: 96%)" in formatted
    assert "Coercive video call demand" in formatted
    assert "0xabcd1234ef567890" in formatted
    assert "1. *Call Ramesh Sharma IMMEDIATELY*" in formatted


def test_telegram_dry_run_mode():
    """Verify that send_alert() returns browser_preview simulation when no API token is configured."""
    svc = TelegramGuardianService(bot_token="", chat_id="")
    res = svc.send_alert(
        victim_name="Anita Roy",
        risk_level="HIGH",
        confidence=0.92,
        case_id="CASE-999"
    )

    assert res["status"] == "simulated"
    assert res["delivered"] is False
    assert res["mode"] == "browser_preview"
    assert "Anita Roy" in res["message"]
    assert "timestamp" in res


def test_telegram_notify_api_endpoint():
    """Verify POST /guardian/notify and POST /guardian/telegram/send endpoints."""
    payload = {
        "victim_name": "Suresh Patel",
        "risk_level": "HIGH",
        "confidence": 0.95,
        "scam_type": "Digital Arrest (Customs Impersonation)",
        "observed_signals": ["Money laundering accusation", "Isolation demand"],
        "case_id": "CASE-TELEGRAM-001",
        "record_hash": "0x7777888899990000"
    }

    # Test /guardian/notify
    resp1 = client.post("/guardian/notify", json=payload)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["status"] in ["simulated", "success", "failed"]
    assert "message" in data1
    assert "telegram" in data1
    assert "Suresh Patel" in data1["telegram"]["message"]

    # Test /guardian/telegram/send
    resp2 = client.post("/guardian/telegram/send", json=payload)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["status"] in ["simulated", "success", "failed"]
    assert "message" in data2
    assert "Suresh Patel" in data2["message"]

    assert "Suresh Patel" in data2["message"]
