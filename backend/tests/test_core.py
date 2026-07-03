# Raksha — Basic Tests
# Validates schemas, store, and orchestrator routing logic.

import json
import pytest
from pathlib import Path
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.schemas import (
    AnalyzeRequest, ClassificationResult, GuidanceResult,
    ComplaintDraft, AuthorityAlert, MetricsResponse, AnalyzeResponse,
    UserDetails,
)


class TestSchemas:
    """Test that Pydantic schemas validate correctly."""

    def test_analyze_request_basic(self):
        req = AnalyzeRequest(text="test message")
        assert req.text == "test message"
        assert req.user_details is None

    def test_analyze_request_with_details(self):
        req = AnalyzeRequest(
            text="test",
            user_details=UserDetails(
                amount_lost="50000",
                suspect_phone="+91-9000012345",
            )
        )
        assert req.user_details.amount_lost == "50000"

    def test_classification_result_scam(self):
        result = ClassificationResult(
            label="SCAM",
            scam_type="digital_arrest",
            confidence=0.95,
            signals=["authority impersonation", "threat of arrest"],
            reasons="This is a digital arrest scam.",
        )
        assert result.label == "SCAM"
        assert result.confidence >= 0.80
        assert len(result.signals) >= 2

    def test_classification_result_safe(self):
        result = ClassificationResult(
            label="SAFE",
            scam_type=None,
            confidence=0.85,
            signals=[],
            reasons="This is a legitimate bank OTP message.",
        )
        assert result.label == "SAFE"

    def test_classification_invalid_label_rejected(self):
        with pytest.raises(Exception):
            ClassificationResult(
                label="INVALID",
                confidence=0.5,
            )

    def test_guidance_result(self):
        result = GuidanceResult(
            headline="You may be targeted by a scam.",
            immediate_action="Do not pay or share any information.",
            steps=["Hang up", "Verify independently", "Call 1930"],
            key_facts=["Digital arrest is not real"],
        )
        assert len(result.steps) == 3

    def test_complaint_draft(self):
        draft = ComplaintDraft(
            category="Online Financial Fraud — Digital Arrest Scam",
            narrative="I received a call claiming to be from CBI...",
        )
        assert "cybercrime.gov.in" in draft.where_to_submit

    def test_authority_alert(self):
        alert = AuthorityAlert(
            scam_type="digital_arrest",
            confidence=0.92,
        )
        assert alert.alert_id  # Should be auto-generated UUID
        assert alert.severity == "medium"
        assert "PII" in alert.privacy_note

    def test_metrics_response_empty(self):
        metrics = MetricsResponse()
        assert metrics.n_test == 0
        assert metrics.false_positive_rate == 0.0
        assert len(metrics.confusion_matrix.labels) == 3

    def test_analyze_response(self):
        cls_result = ClassificationResult(
            label="SAFE", confidence=0.9, signals=[], reasons="OK"
        )
        resp = AnalyzeResponse(
            verdict="SAFE",
            reply_text="This is safe.",
            classification=cls_result,
        )
        assert resp.case_id  # Auto-generated
        assert resp.verdict == "SAFE"


class TestStore:
    """Test the SQLite audit store."""

    def test_log_and_retrieve(self, tmp_path):
        from backend.app.store import AuditStore

        store = AuditStore(db_path=tmp_path / "test.db")

        store.log_case(
            case_id="test-123",
            input_text="Test suspicious message",
            language="en",
            label="SCAM",
            scam_type="digital_arrest",
            confidence=0.95,
            reasons="Test reasons",
            signals=["signal1", "signal2"],
            model_used="gemini-test",
            full_response={"verdict": "SCAM"},
        )

        # Retrieve
        record = store.get_case("test-123")
        assert record is not None
        assert record.case_id == "test-123"
        assert record.label == "SCAM"
        assert record.scam_type == "digital_arrest"

    def test_list_cases(self, tmp_path):
        from backend.app.store import AuditStore

        store = AuditStore(db_path=tmp_path / "test2.db")

        for i in range(5):
            store.log_case(
                case_id=f"case-{i}",
                input_text=f"Message {i}",
                language="en",
                label="SAFE" if i % 2 == 0 else "SCAM",
                scam_type=None if i % 2 == 0 else "kyc_bank",
                confidence=0.8,
                reasons="Test",
                signals=[],
                model_used="test",
                full_response={},
            )

        cases = store.list_cases()
        assert len(cases) == 5
        assert store.count_cases() == 5

    def test_evidence_package(self, tmp_path):
        from backend.app.store import AuditStore

        store = AuditStore(db_path=tmp_path / "test3.db")

        store.log_case(
            case_id="evi-001",
            input_text="Scam message",
            language="hi",
            label="SCAM",
            scam_type="digital_arrest",
            confidence=0.95,
            reasons="Digital arrest scam detected",
            signals=["authority impersonation", "threat"],
            model_used="gemini-2.0-flash",
            full_response={"verdict": "SCAM"},
            guidance_json='{"headline": "This is a scam"}',
        )

        package = store.get_evidence_package("evi-001")
        assert package is not None
        assert package["case_id"] == "evi-001"
        assert package["classification"]["label"] == "SCAM"
        assert package["guidance"]["headline"] == "This is a scam"


class TestMetrics:
    """Test the evaluation metrics computation."""

    def test_perfect_classification(self):
        from backend.app.eval.metrics import compute_metrics

        true = ["SCAM", "SAFE", "UNCERTAIN", "SCAM", "SAFE"]
        pred = ["SCAM", "SAFE", "UNCERTAIN", "SCAM", "SAFE"]

        metrics = compute_metrics(true, pred)
        assert metrics["precision"] == 1.0
        assert metrics["recall"] == 1.0
        assert metrics["f1"] == 1.0
        assert metrics["false_positive_rate"] == 0.0

    def test_false_positive(self):
        from backend.app.eval.metrics import compute_metrics

        true = ["SAFE", "SAFE", "SAFE", "SCAM", "SCAM"]
        pred = ["SCAM", "SAFE", "SAFE", "SCAM", "SCAM"]

        metrics = compute_metrics(true, pred)
        # 1 FP out of 3 non-SCAM = 1/3
        assert abs(metrics["false_positive_rate"] - 1/3) < 0.01

    def test_empty_input(self):
        from backend.app.eval.metrics import compute_metrics

        metrics = compute_metrics([], [])
        assert metrics["n_test"] == 0
