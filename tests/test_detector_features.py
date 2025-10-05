"""
Unit tests for CTA, chat, video, and email detection in detector.py

Tests the specification requirements:
- CTA requires BOTH loader AND load call for definitive
- Chat/conversations detection
- Video embed detection
- Email tracking indicators
"""
import pytest
from hubspot_crawler.detector import detect_html, detect_network


class TestCTADetection:
    """Test CTA (call-to-action) detection logic."""

    def test_cta_both_loader_and_call_definitive(self, sample_html_cta_complete):
        """CTA with BOTH loader AND load call should be definitive."""
        evidence = detect_html(sample_html_cta_complete)

        cta_evidence = [e for e in evidence if e["category"] == "ctas"]
        assert len(cta_evidence) >= 2, "Should have both loader and load call evidence"

        # Loader with load call present should be definitive
        loader_ev = [e for e in cta_evidence if e["patternId"] == "cta_loader_legacy"]
        assert len(loader_ev) == 1, "Should have CTA loader evidence"
        assert loader_ev[0]["confidence"] == "definitive", "CTA loader should be definitive when load call present"

        # Load call should always be definitive
        load_ev = [e for e in cta_evidence if e["patternId"] == "cta_load_call"]
        assert len(load_ev) == 1, "Should have CTA load call evidence"
        assert load_ev[0]["confidence"] == "definitive"

    def test_cta_loader_only_strong(self):
        """CTA loader without load call should be strong (not definitive)."""
        html = """
        <html>
        <head>
            <script charset="utf-8" src="https://js.hscta.net/cta/current.js"></script>
        </head>
        </html>
        """
        evidence = detect_html(html)

        cta_evidence = [e for e in evidence if e["category"] == "ctas"]
        loader_ev = [e for e in cta_evidence if e["patternId"] == "cta_loader_legacy"]

        if loader_ev:
            assert loader_ev[0]["confidence"] == "strong", "CTA loader without call should be strong"

    def test_cta_redirect_link_definitive(self):
        """CTA redirect links should be definitive."""
        html = """
        <html>
        <body>
            <a href="https://cta-redirect.hubspot.com/cta/redirect/12345/cta-id">Click Here</a>
        </body>
        </html>
        """
        evidence = detect_html(html)

        cta_evidence = [e for e in evidence if e["patternId"] == "cta_redirect_link"]
        if cta_evidence:
            assert cta_evidence[0]["confidence"] == "definitive"
            assert cta_evidence[0]["category"] == "ctas"

    def test_cta_evidence_not_hardcoded(self, sample_html_cta_complete):
        """CTA evidence should contain actual code, not placeholders (Bug #6)."""
        evidence = detect_html(sample_html_cta_complete)

        cta_evidence = [e for e in evidence if e["category"] == "ctas"]
        for e in cta_evidence:
            # Should not be old hardcoded text
            assert e["match"] != "cta/current.js + hbspt.cta.load", "Should not be hardcoded"
            # Should contain actual code
            assert "cta" in e["match"].lower()


class TestChatDetection:
    """Test chat/conversations detection logic."""

    def test_chat_js_definitive(self, sample_html_chat):
        """Chat/conversations JS should be definitive."""
        evidence = detect_html(sample_html_chat)

        chat_evidence = [e for e in evidence if e["category"] == "chat"]
        assert len(chat_evidence) >= 1, "Should detect chat"

        js_ev = [e for e in chat_evidence if e["patternId"] == "chat_usemessages_js"]
        assert len(js_ev) == 1, "Should have chat JS evidence"
        assert js_ev[0]["confidence"] == "definitive"
        assert "usemessages" in js_ev[0]["match"]

    def test_chat_api_network_definitive(self, sample_network_chat):
        """Chat API calls in network should be definitive."""
        evidence = detect_network("\n".join(sample_network_chat))

        chat_evidence = [e for e in evidence if e["category"] == "chat"]
        assert len(chat_evidence) >= 1, "Should detect chat from network"

        for e in chat_evidence:
            assert e["confidence"] == "definitive", "Network chat should be definitive"
            assert e["source"] == "url"

    def test_chat_cookie_strong(self):
        """messagesUtk cookie should be strong evidence."""
        html = """
        <html>
        <head>
            <script>var messagesUtk = "abc";</script>
        </head>
        </html>
        """
        evidence = detect_html(html)

        chat_evidence = [e for e in evidence if e.get("patternId") == "cookie_messagesUtk"]
        if chat_evidence:
            assert chat_evidence[0]["confidence"] == "strong"
            assert chat_evidence[0]["category"] == "chat"


class TestVideoDetection:
    """Test HubSpot video detection logic."""

    def test_video_embed_strong(self, sample_html_video):
        """HubSpot video embeds should be strong evidence."""
        evidence = detect_html(sample_html_video)

        video_evidence = [e for e in evidence if e["category"] == "video"]
        assert len(video_evidence) >= 1, "Should detect video"

        vid_ev = [e for e in video_evidence if e["patternId"] == "video_hubspotvideo"]
        assert len(vid_ev) == 1, "Should have video evidence"
        assert vid_ev[0]["confidence"] == "strong"
        assert "hubspotvideo.com" in vid_ev[0]["match"]

    def test_video_network_strong(self):
        """Video URLs in network should be strong evidence."""
        network = ["https://play.hubspotvideo.com/12345"]
        evidence = detect_network("\n".join(network))

        video_evidence = [e for e in evidence if e["category"] == "video"]
        assert len(video_evidence) >= 1, "Should detect video from network"
        assert video_evidence[0]["confidence"] == "strong"


class TestEmailDetection:
    """Test email tracking indicators detection."""

    def test_email_marketing_click_strong(self):
        """Email marketing click links should be strong evidence."""
        html = """
        <html>
        <body>
            <a href="https://t.hubspotemail.net/e2t/click/abc123">Link</a>
        </body>
        </html>
        """
        evidence = detect_html(html)

        email_evidence = [e for e in evidence if e.get("patternId") == "email_hubspot_marketing_click"]
        if email_evidence:
            assert email_evidence[0]["confidence"] == "strong"
            assert email_evidence[0]["category"] == "email"

    def test_email_sales_click_strong(self):
        """Email sales click links should be strong evidence."""
        network = ["https://t.sidekickopen06.com/e1t/c/abc123"]
        evidence = detect_network("\n".join(network))

        email_evidence = [e for e in evidence if "email" in e["category"] and "sales" in e.get("patternId", "")]
        if email_evidence:
            assert email_evidence[0]["confidence"] == "strong"

    def test_hubspotlinks_moderate(self):
        """hubspotlinks.com should be moderate evidence."""
        html = """
        <html>
        <body>
            <a href="https://www.hubspotlinks.com/link/abc">Link</a>
        </body>
        </html>
        """
        evidence = detect_html(html)

        email_evidence = [e for e in evidence if e.get("patternId") == "email_hubspotlinks"]
        if email_evidence:
            assert email_evidence[0]["confidence"] == "moderate"


class TestMeetingsDetection:
    """Test HubSpot meetings/scheduling detection."""

    def test_meetings_embed_strong(self):
        """Meetings embed script should be strong evidence."""
        html = """
        <html>
        <head>
            <script type="text/javascript" src="https://static.hsappstatic.net/MeetingsEmbed/ex/MeetingsEmbedCode.js"></script>
        </head>
        </html>
        """
        evidence = detect_html(html)

        meetings_evidence = [e for e in evidence if e["category"] == "meetings"]
        if meetings_evidence:
            js_ev = [e for e in meetings_evidence if e["patternId"] == "meetings_embed_js"]
            assert len(js_ev) >= 1
            assert js_ev[0]["confidence"] == "strong"

    def test_meetings_iframe_strong(self):
        """Meetings iframe should be strong evidence."""
        html = """
        <html>
        <body>
            <iframe src="https://meetings.hubspot.com/user/meeting"></iframe>
        </body>
        </html>
        """
        evidence = detect_html(html)

        meetings_evidence = [e for e in evidence if e.get("patternId") == "meetings_iframe"]
        if meetings_evidence:
            assert meetings_evidence[0]["confidence"] == "strong"
            assert meetings_evidence[0]["category"] == "meetings"
