"""
Tests for CSV output format (Phase 6.6).

Covers:
- CSV flattening function
- Column structure
- Boolean formatting
- Hub IDs formatting
- Null/None handling
- Evidence counting
- End-to-end CSV generation
"""

import pytest
import csv
import io
from hubspot_crawler.crawler import flatten_result_for_csv
from hubspot_crawler.detector import make_result


class TestFlattenResultForCSV:
    """Test the flatten_result_for_csv function"""

    def test_basic_flattening(self):
        """Should flatten a basic result structure"""
        evidence = []
        result = make_result("https://example.com", evidence)

        flat = flatten_result_for_csv(result)

        assert flat["url"] == "https://example.com"
        assert "timestamp" in flat
        assert flat["hubspot_detected"] is False
        assert flat["tracking"] is False
        assert flat["cms_hosting"] is False

    def test_boolean_values_preserved(self):
        """Booleans should remain as Python bool (True/False)"""
        evidence = [{
            "category": "tracking",
            "patternId": "tracking_loader_script",
            "match": "js.hs-scripts.com/123.js",
            "source": "html",
            "hubId": 123,
            "confidence": "definitive"
        }]
        result = make_result("https://example.com", evidence)

        flat = flatten_result_for_csv(result)

        assert flat["hubspot_detected"] is True
        assert flat["tracking"] is True
        assert isinstance(flat["hubspot_detected"], bool)
        assert isinstance(flat["tracking"], bool)

    def test_hub_ids_formatting_single(self):
        """Single Hub ID should be formatted as string"""
        evidence = [{
            "category": "tracking",
            "patternId": "tracking_loader_script",
            "match": "js.hs-scripts.com/123.js",
            "source": "html",
            "hubId": 123,
            "confidence": "definitive"
        }]
        result = make_result("https://example.com", evidence)

        flat = flatten_result_for_csv(result)

        assert flat["hub_ids"] == "123"
        assert flat["hub_id_count"] == 1

    def test_hub_ids_formatting_multiple(self):
        """Multiple Hub IDs should be comma-separated"""
        evidence = [
            {
                "category": "tracking",
                "patternId": "tracking_loader_script",
                "match": "js.hs-scripts.com/123.js",
                "source": "html",
                "hubId": 123,
                "confidence": "definitive"
            },
            {
                "category": "tracking",
                "patternId": "tracking_analytics",
                "match": "analytics/456.js",
                "source": "html",
                "hubId": 456,
                "confidence": "strong"
            }
        ]
        result = make_result("https://example.com", evidence)

        flat = flatten_result_for_csv(result)

        assert flat["hub_ids"] == "123,456"
        assert flat["hub_id_count"] == 2

    def test_hub_ids_empty(self):
        """Empty Hub IDs should be empty string"""
        evidence = []
        result = make_result("https://example.com", evidence)

        flat = flatten_result_for_csv(result)

        assert flat["hub_ids"] == ""
        assert flat["hub_id_count"] == 0

    def test_all_features_present(self):
        """All feature columns should be present"""
        evidence = []
        result = make_result("https://example.com", evidence)

        flat = flatten_result_for_csv(result)

        assert "forms" in flat
        assert "chat" in flat
        assert "ctas_legacy" in flat
        assert "meetings" in flat
        assert "video" in flat
        assert "email_tracking" in flat

    def test_features_true_when_detected(self):
        """Features should be True when detected"""
        evidence = [
            {
                "category": "forms",
                "patternId": "forms_loader_script",
                "match": "js.hsforms.net",
                "source": "html",
                "hubId": None,
                "confidence": "strong"
            },
            {
                "category": "chat",
                "patternId": "chat_js",
                "match": "conversations/embed.js",
                "source": "html",
                "hubId": None,
                "confidence": "definitive"
            }
        ]
        result = make_result("https://example.com", evidence)

        flat = flatten_result_for_csv(result)

        assert flat["forms"] is True
        assert flat["chat"] is True
        assert flat["video"] is False

    def test_evidence_count(self):
        """Should count evidence items correctly"""
        evidence = [
            {"category": "tracking", "patternId": "test1", "match": "m1", "source": "html", "hubId": None, "confidence": "strong"},
            {"category": "cms", "patternId": "test2", "match": "m2", "source": "html", "hubId": None, "confidence": "strong"},
            {"category": "forms", "patternId": "test3", "match": "m3", "source": "html", "hubId": None, "confidence": "strong"}
        ]
        result = make_result("https://example.com", evidence)

        flat = flatten_result_for_csv(result)

        assert flat["evidence_count"] == 3

    def test_http_status_present(self):
        """HTTP status should be included when provided"""
        evidence = []
        result = make_result("https://example.com", evidence, http_status=200)

        flat = flatten_result_for_csv(result)

        assert flat["http_status"] == 200

    def test_http_status_missing(self):
        """HTTP status should be empty string when not provided"""
        evidence = []
        result = make_result("https://example.com", evidence)

        flat = flatten_result_for_csv(result)

        assert flat["http_status"] == ""

    def test_page_metadata_present(self):
        """Page metadata should be included when provided"""
        evidence = []
        metadata = {"title": "Test Page", "description": "Test description"}
        result = make_result("https://example.com", evidence, page_metadata=metadata)

        flat = flatten_result_for_csv(result)

        assert flat["page_title"] == "Test Page"
        assert flat["page_description"] == "Test description"

    def test_page_metadata_null_values(self):
        """Should handle null metadata values"""
        evidence = []
        metadata = {"title": None, "description": None}
        result = make_result("https://example.com", evidence, page_metadata=metadata)

        flat = flatten_result_for_csv(result)

        assert flat["page_title"] == ""
        assert flat["page_description"] == ""

    def test_page_metadata_missing(self):
        """Should handle missing page_metadata"""
        evidence = []
        result = make_result("https://example.com", evidence)

        flat = flatten_result_for_csv(result)

        assert flat["page_title"] == ""
        assert flat["page_description"] == ""

    def test_confidence_values(self):
        """Should include confidence level"""
        evidence = [{
            "category": "tracking",
            "patternId": "tracking_loader_script",
            "match": "js.hs-scripts.com/123.js",
            "source": "html",
            "hubId": 123,
            "confidence": "definitive"
        }]
        result = make_result("https://example.com", evidence)

        flat = flatten_result_for_csv(result)

        assert flat["confidence"] == "definitive"  # Overall confidence from summarise()

    def test_all_expected_columns(self):
        """Should have exactly the expected columns"""
        evidence = []
        result = make_result("https://example.com", evidence)

        flat = flatten_result_for_csv(result)

        expected_columns = [
            "url", "timestamp", "hubspot_detected", "tracking", "cms_hosting", "confidence",
            "forms", "chat", "ctas_legacy", "meetings", "video", "email_tracking",
            "hub_ids", "hub_id_count", "evidence_count", "http_status", "page_title", "page_description"
        ]

        assert set(flat.keys()) == set(expected_columns)
        assert len(flat) == 18
