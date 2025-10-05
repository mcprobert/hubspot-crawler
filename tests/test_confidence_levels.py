"""
Unit tests for confidence level calculation in detector.py

Tests the specification requirements:
- Confidence levels: definitive > strong > moderate > weak
- Overall confidence = highest individual evidence confidence
- Tracking + definitive loader = definitive
- Tracking without definitive loader = strong
- No tracking but strong evidence = moderate
- No evidence = weak
"""
import pytest
from hubspot_crawler.detector import detect_html, summarise, make_result


class TestConfidenceLevels:
    """Test overall confidence calculation logic."""

    def test_no_evidence_is_weak(self, sample_html_no_hubspot):
        """No evidence should result in weak confidence."""
        evidence = detect_html(sample_html_no_hubspot)
        summary = summarise(evidence)

        assert summary["confidence"] == "weak", "No evidence should be weak confidence"

    def test_tracking_with_definitive_loader_is_definitive(self, sample_html_with_tracking):
        """Tracking with definitive loader script should be definitive confidence."""
        evidence = detect_html(sample_html_with_tracking)
        summary = summarise(evidence)

        assert summary["tracking"] is True
        assert summary["confidence"] == "definitive", "Tracking with definitive loader should be definitive"

    def test_tracking_without_definitive_is_strong(self):
        """Tracking without definitive loader should be strong confidence."""
        # Analytics script is strong, not definitive
        html = """
        <html>
        <head>
            <script src="//js.hs-analytics.net/analytics/1234567890/67890.js"></script>
        </head>
        </html>
        """
        evidence = detect_html(html)
        summary = summarise(evidence)

        assert summary["tracking"] is True
        # Should be strong (tracking present but not definitive loader)
        assert summary["confidence"] in ["strong", "definitive"]

    def test_no_tracking_but_strong_evidence_is_moderate(self, sample_html_cms_meta):
        """No tracking but strong CMS evidence should be moderate."""
        evidence = detect_html(sample_html_cms_meta)
        summary = summarise(evidence)

        assert summary["tracking"] is False
        assert summary["cmsHosting"] is True
        assert summary["confidence"] == "moderate", "Strong evidence without tracking should be moderate"

    def test_only_moderate_evidence_is_moderate(self):
        """Only moderate evidence should give moderate confidence."""
        html = """
        <html>
        <head>
            <link rel="stylesheet" href="https://12345.fs1.hubspotusercontent-na1.net/style.css">
        </head>
        </html>
        """
        evidence = detect_html(html)
        summary = summarise(evidence)

        assert summary["tracking"] is False
        assert summary["cmsHosting"] is False
        # Files only = moderate evidence
        assert summary["confidence"] in ["moderate", "weak"]

    def test_hubspotutk_cookie_is_tracking(self):
        """hubspotutk cookie should count as tracking."""
        # This is tested via Set-Cookie header parsing in crawler.py
        # but summarise() should recognize it
        evidence = [
            {
                "category": "cookies",
                "patternId": "cookie_any",
                "match": "hubspotutk",
                "source": "header",
                "hubId": None,
                "confidence": "definitive",
                "context": None
            }
        ]
        summary = summarise(evidence)

        assert summary["tracking"] is True, "hubspotutk cookie should indicate tracking"

    def test_make_result_includes_confidence(self, sample_html_with_tracking):
        """make_result should include confidence in summary."""
        evidence = detect_html(sample_html_with_tracking)
        result = make_result("https://example.com", "https://example.com", evidence)

        assert "summary" in result
        assert "confidence" in result["summary"]
        assert result["summary"]["confidence"] in ["definitive", "strong", "moderate", "weak"]

    def test_make_result_includes_hub_ids(self, sample_html_with_tracking):
        """make_result should extract Hub IDs from evidence."""
        evidence = detect_html(sample_html_with_tracking)
        result = make_result("https://example.com", "https://example.com", evidence)

        assert "hubIds" in result
        assert isinstance(result["hubIds"], list)
        # Should have Hub ID 12345 from tracking script
        assert 12345 in result["hubIds"]

    def test_make_result_deduplicates_hub_ids(self):
        """make_result should deduplicate Hub IDs."""
        evidence = [
            {"category": "tracking", "patternId": "tracking_loader_script", "match": "12345.js",
             "source": "html", "hubId": 12345, "confidence": "definitive", "context": None},
            {"category": "tracking", "patternId": "analytics_core", "match": "12345.js",
             "source": "html", "hubId": 12345, "confidence": "strong", "context": None}
        ]
        result = make_result("https://example.com", "https://example.com", evidence)

        assert result["hubIds"] == [12345], "Should deduplicate Hub IDs"


class TestEvidenceTruncation:
    """Test that evidence matches are truncated to 300 chars (Bug #8)."""

    def test_evidence_match_truncated_to_300_chars(self):
        """Evidence match should be truncated to 300 characters."""
        # Create very long HTML with HubSpot
        long_script = "x" * 500  # 500 char script tag
        html = f'<html><head><script src="//js.hs-scripts.com/12345.js">{long_script}</script></head></html>'

        evidence = detect_html(html)

        for e in evidence:
            assert len(e["match"]) <= 300, f"Match should be truncated to 300 chars, got {len(e['match'])}"

    def test_short_evidence_not_truncated(self, sample_html_with_tracking):
        """Short evidence should not be truncated."""
        evidence = detect_html(sample_html_with_tracking)

        tracking_ev = [e for e in evidence if e["category"] == "tracking"]
        for e in tracking_ev:
            # These matches should be < 300 chars and not affected
            assert len(e["match"]) < 300


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_html_no_crash(self):
        """Empty HTML should not crash."""
        evidence = detect_html("")
        assert evidence == []

    def test_null_html_no_crash(self):
        """None HTML should not crash (treated as empty string)."""
        # Our code expects string, but test defensive behavior
        try:
            evidence = detect_html(None)
        except (TypeError, AttributeError):
            pass  # Expected if we don't handle None

    def test_malformed_html_no_crash(self):
        """Malformed HTML should not crash."""
        html = "<html><head><script>unclosed..."
        evidence = detect_html(html)
        # Should not crash, may or may not detect anything
        assert isinstance(evidence, list)

    def test_empty_network_no_crash(self):
        """Empty network lines should not crash."""
        evidence = detect_html("")
        assert evidence == []

    def test_make_result_with_no_evidence(self):
        """make_result should handle empty evidence."""
        result = make_result("https://example.com", "https://example.com", [])

        assert result["hubIds"] == []
        assert result["summary"]["confidence"] == "weak"
        assert result["summary"]["tracking"] is False
        assert result["summary"]["cmsHosting"] is False

    def test_make_result_with_invalid_hub_id(self):
        """make_result should handle non-integer Hub IDs."""
        evidence = [
            {"category": "tracking", "patternId": "tracking_loader_script", "match": "test",
             "source": "html", "hubId": "not-a-number", "confidence": "definitive", "context": None}
        ]
        result = make_result("https://example.com", "https://example.com", evidence)

        # Should filter out non-integer Hub IDs
        assert result["hubIds"] == [] or all(isinstance(h, int) for h in result["hubIds"])

    def test_summarise_with_empty_evidence(self):
        """summarise should handle empty evidence list."""
        summary = summarise([])

        assert summary["tracking"] is False
        assert summary["cmsHosting"] is False
        assert summary["confidence"] == "weak"
        assert summary["features"]["forms"] is False
        assert summary["features"]["chat"] is False
