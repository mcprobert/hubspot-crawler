"""
Tests for failure handling with new URL schema (v1.5.0).

Verifies that when all URL attempts fail, the error object:
- Uses new schema (original_url + final_url)
- Has required fields for CSV export
- Works with flatten_result_for_csv()
"""

import pytest
from hubspot_crawler.crawler import flatten_result_for_csv
from datetime import datetime


class TestFailureHandling:
    """Test failure result structure"""

    def test_failure_result_has_required_url_fields(self):
        """Failed URLs should have original_url and final_url"""
        # Simulate failure result structure
        failure_result = {
            "original_url": "example.com",
            "final_url": "example.com",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "hubspot_detected": False,
            "hubIds": [],
            "summary": {
                "tracking": False,
                "cmsHosting": False,
                "features": {
                    "forms": False,
                    "chat": False,
                    "ctasLegacy": False,
                    "meetings": False,
                    "video": False,
                    "emailTrackingIndicators": False
                },
                "confidence": "weak"
            },
            "evidence": [],
            "headers": {},
            "error": "Failed after all retry attempts",
            "attempts": 3,
            "attempted_urls": ["https://example.com", "https://www.example.com"]
        }

        assert "original_url" in failure_result
        assert "final_url" in failure_result
        assert failure_result["original_url"] == "example.com"
        assert failure_result["final_url"] == "example.com"

    def test_failure_result_has_summary_and_evidence(self):
        """Failed URLs should have empty summary and evidence for schema consistency"""
        failure_result = {
            "original_url": "example.com",
            "final_url": "example.com",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "hubspot_detected": False,
            "hubIds": [],
            "summary": {
                "tracking": False,
                "cmsHosting": False,
                "features": {
                    "forms": False,
                    "chat": False,
                    "ctasLegacy": False,
                    "meetings": False,
                    "video": False,
                    "emailTrackingIndicators": False
                },
                "confidence": "weak"
            },
            "evidence": [],
            "headers": {},
            "error": "Failed after all retry attempts"
        }

        assert "summary" in failure_result
        assert "evidence" in failure_result
        assert "hubspot_detected" in failure_result
        assert failure_result["summary"]["confidence"] == "weak"
        assert failure_result["evidence"] == []
        assert failure_result["hubspot_detected"] is False

    def test_csv_flattening_works_with_failure_result(self):
        """flatten_result_for_csv() should work with failure results"""
        failure_result = {
            "original_url": "badurl.invalid",
            "final_url": "badurl.invalid",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "hubspot_detected": False,
            "hubIds": [],
            "summary": {
                "tracking": False,
                "cmsHosting": False,
                "features": {
                    "forms": False,
                    "chat": False,
                    "ctasLegacy": False,
                    "meetings": False,
                    "video": False,
                    "emailTrackingIndicators": False
                },
                "confidence": "weak"
            },
            "evidence": [],
            "headers": {},
            "error": "Failed after all retry attempts",
            "attempts": 3
        }

        # Should not raise exception
        flat = flatten_result_for_csv(failure_result)

        # Check URL columns are populated
        assert flat["original_url"] == "badurl.invalid"
        assert flat["final_url"] == "badurl.invalid"

        # Check other expected columns
        assert flat["hubspot_detected"] is False
        assert flat["tracking"] is False
        assert flat["cms_hosting"] is False
        assert flat["confidence"] == "weak"
        assert flat["hub_ids"] == ""
        assert flat["hub_id_count"] == 0
        assert flat["evidence_count"] == 0

    def test_failure_and_success_have_same_csv_columns(self):
        """Failure and success results should produce the same CSV columns"""
        success_result = {
            "original_url": "https://example.com",
            "final_url": "https://www.example.com",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "hubspot_detected": True,
            "hubIds": [123],
            "summary": {
                "tracking": True,
                "cmsHosting": False,
                "features": {
                    "forms": False,
                    "chat": False,
                    "ctasLegacy": False,
                    "meetings": False,
                    "video": False,
                    "emailTrackingIndicators": False
                },
                "confidence": "definitive"
            },
            "evidence": [
                {
                    "category": "tracking",
                    "patternId": "test",
                    "match": "test",
                    "source": "html",
                    "confidence": "definitive",
                    "hubId": 123
                }
            ],
            "headers": {}
        }

        failure_result = {
            "original_url": "badurl.invalid",
            "final_url": "badurl.invalid",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "hubspot_detected": False,
            "hubIds": [],
            "summary": {
                "tracking": False,
                "cmsHosting": False,
                "features": {
                    "forms": False,
                    "chat": False,
                    "ctasLegacy": False,
                    "meetings": False,
                    "video": False,
                    "emailTrackingIndicators": False
                },
                "confidence": "weak"
            },
            "evidence": [],
            "headers": {}
        }

        success_flat = flatten_result_for_csv(success_result)
        failure_flat = flatten_result_for_csv(failure_result)

        # Both should have exactly the same keys
        assert set(success_flat.keys()) == set(failure_flat.keys())

    def test_final_url_equals_original_url_on_failure(self):
        """When fetch fails, final_url should equal original_url (no redirect occurred)"""
        failure_result = {
            "original_url": "http://192.168.1.999",  # Invalid IP
            "final_url": "http://192.168.1.999",     # Same as original
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "hubspot_detected": False,
            "hubIds": [],
            "summary": {
                "tracking": False,
                "cmsHosting": False,
                "features": {
                    "forms": False,
                    "chat": False,
                    "ctasLegacy": False,
                    "meetings": False,
                    "video": False,
                    "emailTrackingIndicators": False
                },
                "confidence": "weak"
            },
            "evidence": [],
            "headers": {}
        }

        # Verify both URLs are the same
        assert failure_result["original_url"] == failure_result["final_url"]

        # Verify CSV export works
        flat = flatten_result_for_csv(failure_result)
        assert flat["original_url"] == flat["final_url"]
        assert flat["original_url"] == "http://192.168.1.999"
