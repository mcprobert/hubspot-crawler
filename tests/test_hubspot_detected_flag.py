"""
Tests for hubspot_detected flag (Phase 6.5).

Covers:
- hubspot_detected is True when tracking detected
- hubspot_detected is True when CMS detected
- hubspot_detected is True when any feature detected
- hubspot_detected is False when no HubSpot detected
- hubspot_detected is at top level of result
"""

import pytest
from hubspot_crawler.detector import make_result, detect_html


class TestHubSpotDetectedFlag:
    """Test the hubspot_detected boolean flag"""

    def test_true_when_tracking_detected(self):
        """hubspot_detected should be True when tracking is detected"""
        evidence = [{
            "category": "tracking",
            "patternId": "tracking_loader_script",
            "match": "js.hs-scripts.com/123.js",
            "source": "html",
            "hubId": 123,
            "confidence": "definitive"
        }]
        result = make_result("https://example.com", evidence)

        assert result["hubspot_detected"] is True
        assert result["summary"]["tracking"] is True

    def test_true_when_cms_detected(self):
        """hubspot_detected should be True when CMS hosting is detected"""
        evidence = [{
            "category": "cms",
            "patternId": "cms_meta_generator",
            "match": '<meta name="generator" content="HubSpot"',
            "source": "html",
            "hubId": None,
            "confidence": "strong"
        }]
        result = make_result("https://example.com", evidence)

        assert result["hubspot_detected"] is True
        assert result["summary"]["cmsHosting"] is True

    def test_true_when_forms_detected(self):
        """hubspot_detected should be True when forms feature is detected"""
        evidence = [{
            "category": "forms",
            "patternId": "forms_loader_script",
            "match": "js.hsforms.net/forms",
            "source": "html",
            "hubId": None,
            "confidence": "strong"
        }]
        result = make_result("https://example.com", evidence)

        assert result["hubspot_detected"] is True
        assert result["summary"]["features"]["forms"] is True

    def test_true_when_chat_detected(self):
        """hubspot_detected should be True when chat feature is detected"""
        evidence = [{
            "category": "chat",
            "patternId": "chat_js",
            "match": "js.hs-scripts.com/conversations/embed.js",
            "source": "html",
            "hubId": None,
            "confidence": "definitive"
        }]
        result = make_result("https://example.com", evidence)

        assert result["hubspot_detected"] is True
        assert result["summary"]["features"]["chat"] is True

    def test_true_when_video_detected(self):
        """hubspot_detected should be True when video feature is detected"""
        evidence = [{
            "category": "video",
            "patternId": "video_hubspotvideo",
            "match": "play.hubspotvideo.com/embed",
            "source": "html",
            "hubId": None,
            "confidence": "strong"
        }]
        result = make_result("https://example.com", evidence)

        assert result["hubspot_detected"] is True
        assert result["summary"]["features"]["video"] is True

    def test_true_when_meetings_detected(self):
        """hubspot_detected should be True when meetings feature is detected"""
        evidence = [{
            "category": "meetings",
            "patternId": "meetings_embed",
            "match": "meetings.hubspot.com/embed",
            "source": "html",
            "hubId": None,
            "confidence": "strong"
        }]
        result = make_result("https://example.com", evidence)

        assert result["hubspot_detected"] is True
        assert result["summary"]["features"]["meetings"] is True

    def test_false_when_no_hubspot(self):
        """hubspot_detected should be False when no HubSpot is detected"""
        evidence = []
        result = make_result("https://example.com", evidence)

        assert result["hubspot_detected"] is False
        assert result["summary"]["tracking"] is False
        assert result["summary"]["cmsHosting"] is False
        assert not any(result["summary"]["features"].values())

    def test_true_when_multiple_signals(self):
        """hubspot_detected should be True when multiple HubSpot signals present"""
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
                "category": "cms",
                "patternId": "cms_meta_generator",
                "match": '<meta name="generator" content="HubSpot"',
                "source": "html",
                "hubId": None,
                "confidence": "strong"
            },
            {
                "category": "forms",
                "patternId": "forms_loader_script",
                "match": "js.hsforms.net/forms",
                "source": "html",
                "hubId": None,
                "confidence": "strong"
            }
        ]
        result = make_result("https://example.com", evidence)

        assert result["hubspot_detected"] is True
        assert result["summary"]["tracking"] is True
        assert result["summary"]["cmsHosting"] is True
        assert result["summary"]["features"]["forms"] is True

    def test_field_at_top_level(self):
        """hubspot_detected should be at top level of result, not in summary"""
        evidence = [{
            "category": "tracking",
            "patternId": "tracking_loader_script",
            "match": "js.hs-scripts.com/123.js",
            "source": "html",
            "hubId": 123,
            "confidence": "definitive"
        }]
        result = make_result("https://example.com", evidence)

        # Check it's at top level
        assert "hubspot_detected" in result
        assert result["hubspot_detected"] is True

        # Check it's NOT in summary
        assert "hubspot_detected" not in result["summary"]

    def test_with_real_html_tracking(self, sample_html_with_tracking):
        """Test hubspot_detected with real HTML containing tracking"""
        evidence = detect_html(sample_html_with_tracking)
        result = make_result("https://example.com", evidence)

        assert result["hubspot_detected"] is True

    def test_with_real_html_forms(self, sample_html_forms_complete):
        """Test hubspot_detected with real HTML containing forms"""
        evidence = detect_html(sample_html_forms_complete)
        result = make_result("https://example.com", evidence)

        assert result["hubspot_detected"] is True

    def test_with_clean_html(self):
        """Test hubspot_detected with clean HTML (no HubSpot)"""
        html = "<html><head><title>Clean Page</title></head><body>No HubSpot</body></html>"
        evidence = detect_html(html)
        result = make_result("https://example.com", evidence)

        assert result["hubspot_detected"] is False
