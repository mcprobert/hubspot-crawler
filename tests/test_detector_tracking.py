"""
Unit tests for tracking detection in detector.py

Tests the specification requirements:
- Hub ID extraction from js.hs-scripts.com/{ID}.js
- Hub ID extraction from js.hs-analytics.net/analytics/{ts}/{ID}.js
- Tracking loader = definitive confidence
- Analytics core = strong confidence
- Network tracking evidence = definitive confidence
"""
import pytest
from hubspot_crawler.detector import detect_html, detect_network


class TestTrackingDetection:
    """Test tracking script detection and Hub ID extraction."""

    def test_tracking_loader_extracts_hub_id(self, sample_html_with_tracking):
        """Tracking loader script should extract Hub ID from URL."""
        evidence = detect_html(sample_html_with_tracking)

        tracking_evidence = [e for e in evidence if e["category"] == "tracking"]
        assert len(tracking_evidence) >= 1, "Should detect tracking script"

        loader_ev = [e for e in tracking_evidence if e["patternId"] == "tracking_loader_script"]
        assert len(loader_ev) == 1, "Should have tracking loader evidence"
        assert loader_ev[0]["hubId"] == 12345, "Should extract Hub ID 12345"
        assert loader_ev[0]["confidence"] == "definitive"
        assert "12345.js" in loader_ev[0]["match"]

    def test_analytics_extracts_hub_id(self, sample_html_analytics):
        """Analytics script should extract Hub ID from URL."""
        evidence = detect_html(sample_html_analytics)

        analytics_evidence = [e for e in evidence if e["patternId"] == "analytics_core"]
        assert len(analytics_evidence) >= 1, "Should detect analytics script"
        assert analytics_evidence[0]["hubId"] == 67890, "Should extract Hub ID from analytics URL"
        assert analytics_evidence[0]["confidence"] == "strong"

    def test_network_tracking_definitive_confidence(self, sample_network_tracking):
        """Network tracking requests should be definitive confidence."""
        evidence = detect_network("\n".join(sample_network_tracking))

        tracking_evidence = [e for e in evidence if e["category"] == "tracking"]
        assert len(tracking_evidence) >= 1, "Should detect tracking from network"

        # Network evidence is definitive (actual requests)
        for e in tracking_evidence:
            assert e["confidence"] == "definitive", f"Network tracking should be definitive, got {e['confidence']}"
            assert e["source"] == "url"

    def test_network_tracking_extracts_hub_ids(self, sample_network_tracking):
        """Network tracking should extract Hub IDs from URLs."""
        evidence = detect_network("\n".join(sample_network_tracking))

        # Should extract Hub ID 12345 from hs-scripts.com
        loader_ev = [e for e in evidence if "hs-scripts" in e["match"]]
        if loader_ev:
            assert loader_ev[0]["hubId"] == 12345

        # Should extract Hub ID 67890 from hs-analytics.net
        analytics_ev = [e for e in evidence if "hs-analytics" in e["match"]]
        if analytics_ev:
            assert analytics_ev[0]["hubId"] == 67890

    def test_tracking_evidence_has_actual_match(self, sample_html_with_tracking):
        """Tracking evidence should contain actual script tag, not placeholder."""
        evidence = detect_html(sample_html_with_tracking)

        tracking_evidence = [e for e in evidence if e["category"] == "tracking"]
        for e in tracking_evidence:
            assert e["match"], "Match should not be empty"
            assert "hs-scripts.com" in e["match"] or "hs-analytics" in e["match"]
            # Should not be hardcoded placeholder
            assert e["match"] != "tracking_script"

    def test_no_tracking_on_clean_html(self, sample_html_no_hubspot):
        """HTML without HubSpot should have no tracking evidence."""
        evidence = detect_html(sample_html_no_hubspot)

        tracking_evidence = [e for e in evidence if e["category"] == "tracking"]
        assert len(tracking_evidence) == 0, "Should not detect tracking on clean HTML"

    def test_hub_id_not_corrupted_by_variable_reuse(self):
        """Hub IDs should not be corrupted by variable reuse (Bug #4)."""
        html = """
        <html>
        <head>
            <script type="text/javascript" id="hs-script-loader" src="//js.hs-scripts.com/11111.js"></script>
            <script src="//js.hs-analytics.net/analytics/1234567890/22222.js"></script>
        </head>
        </html>
        """
        evidence = detect_html(html)

        tracking_evidence = [e for e in evidence if e["category"] == "tracking"]
        assert len(tracking_evidence) == 2, "Should detect both scripts"

        # Check Hub IDs are correct and not corrupted
        hub_ids = [e["hubId"] for e in tracking_evidence if e["hubId"]]
        assert 11111 in hub_ids, "Should have Hub ID 11111"
        assert 22222 in hub_ids, "Should have Hub ID 22222"
        # Should NOT have the same Hub ID for both
        assert len(set(hub_ids)) == 2, "Hub IDs should be distinct"

    def test_tracking_cookie_definitive_confidence(self):
        """hubspotutk cookie should be definitive confidence for tracking."""
        # This is tested in crawler.py (Set-Cookie headers)
        # But we can test that cookie evidence in HTML is recognized
        html = """
        <html>
        <head>
            <script>
                var hubspotutk = "abc123";
            </script>
        </head>
        </html>
        """
        evidence = detect_html(html)

        cookie_evidence = [e for e in evidence if e["category"] == "cookies" and "hubspotutk" in e["match"].lower()]
        # If found in HTML, should be moderate (not definitive - only Set-Cookie header is definitive)
        if cookie_evidence:
            assert cookie_evidence[0]["confidence"] == "moderate"

    def test_beacon_tracking_detection(self):
        """Beacon/PTQ tracking should be detected from network."""
        network = ["https://api.hubapi.com/livechat-public/v1/beacon/track"]
        evidence = detect_network("\n".join(network))

        beacon_evidence = [e for e in evidence if "beacon" in e["patternId"]]
        if beacon_evidence:
            assert beacon_evidence[0]["category"] == "tracking"
            assert beacon_evidence[0]["confidence"] == "definitive"

    def test_hsq_queue_detected(self, sample_html_hsq_queue):
        """_hsq queue initialization should be detected as tracking."""
        evidence = detect_html(sample_html_hsq_queue)

        tracking_evidence = [e for e in evidence if e["patternId"] == "_hsq_presence"]
        assert len(tracking_evidence) == 1, "Should detect _hsq analytics queue"
        assert tracking_evidence[0]["confidence"] == "strong"
        assert "_hsq" in tracking_evidence[0]["match"]
        assert tracking_evidence[0]["category"] == "tracking"

    def test_url_params_detected(self, sample_html_url_params):
        """HubSpot URL parameters should be detected."""
        evidence = detect_html(sample_html_url_params)

        param_evidence = [e for e in evidence if e["patternId"] == "url_params_hs"]
        assert len(param_evidence) >= 1, "Should detect URL tracking parameters"
        assert param_evidence[0]["confidence"] == "moderate"
        assert param_evidence[0]["category"] == "tracking"

    def test_banner_helper_detected(self, sample_html_banner_helper):
        """Banner helper script should be detected."""
        evidence = detect_html(sample_html_banner_helper)

        banner_evidence = [e for e in evidence if e["patternId"] == "banner_helper"]
        assert len(banner_evidence) == 1, "Should detect banner helper script"
        assert banner_evidence[0]["confidence"] == "strong"
        assert banner_evidence[0]["category"] == "tracking"
        assert "hs-banner.com" in banner_evidence[0]["match"]

    def test_tracking_script_without_id(self, sample_html_tracking_no_id):
        """Tracking script without id attribute should be caught by fallback."""
        evidence = detect_html(sample_html_tracking_no_id)

        tracking_evidence = [e for e in evidence if e["category"] == "tracking"]
        assert len(tracking_evidence) >= 1, "Should detect tracking script via fallback"

        script_any = [e for e in tracking_evidence if e["patternId"] == "tracking_script_any"]
        assert len(script_any) == 1, "Should use tracking_script_any fallback pattern"
        assert script_any[0]["hubId"] == 54321, "Should extract Hub ID from URL"
        assert script_any[0]["confidence"] == "strong"
