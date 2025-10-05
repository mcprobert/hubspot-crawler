"""
Unit tests for CMS detection in detector.py

Tests the specification requirements:
- CMS hosting = meta generator=HubSpot OR (hs_cos_wrapper class AND /_hcms/ path)
- Files CDN = moderate confidence (files hosted ≠ CMS)
"""
import pytest
from hubspot_crawler.detector import detect_html, detect_network


class TestCMSDetection:
    """Test CMS hosting detection logic."""

    def test_cms_meta_generator_strong(self, sample_html_cms_meta):
        """Meta generator=HubSpot should give strong CMS evidence."""
        evidence = detect_html(sample_html_cms_meta)

        cms_evidence = [e for e in evidence if e["category"] == "cms"]
        assert len(cms_evidence) >= 1, "Should detect CMS from meta generator"

        meta_ev = [e for e in cms_evidence if e["patternId"] == "cms_meta_generator"]
        assert len(meta_ev) == 1, "Should have meta generator evidence"
        assert meta_ev[0]["confidence"] == "strong"
        assert "generator" in meta_ev[0]["match"].lower()

    def test_cms_wrapper_with_hcms_strong(self, sample_html_cms_wrapper_with_hcms):
        """Wrapper class + /_hcms/ path should give strong CMS evidence."""
        evidence = detect_html(sample_html_cms_wrapper_with_hcms)

        cms_evidence = [e for e in evidence if e["category"] == "cms"]
        assert len(cms_evidence) >= 1, "Should detect CMS from wrapper + /_hcms/"

        wrapper_ev = [e for e in cms_evidence if e["patternId"] == "cms_wrapper_with_hcms"]
        assert len(wrapper_ev) == 1, "Should have wrapper evidence"
        assert wrapper_ev[0]["confidence"] == "strong"
        assert "hs_cos_wrapper" in wrapper_ev[0]["match"]

    def test_cms_wrapper_without_hcms_no_cms(self, sample_html_cms_wrapper_no_hcms):
        """Wrapper class WITHOUT /_hcms/ path should NOT give CMS evidence."""
        evidence = detect_html(sample_html_cms_wrapper_no_hcms)

        # Should not create cms_wrapper_with_hcms evidence (requires both conditions)
        wrapper_ev = [e for e in evidence if e.get("patternId") == "cms_wrapper_with_hcms"]
        assert len(wrapper_ev) == 0, "Should not detect CMS without /_hcms/ path"

    def test_files_cdn_moderate_confidence(self):
        """Files hosted on hubspotusercontent should be moderate confidence."""
        html = """
        <html>
        <head>
            <link rel="stylesheet" href="https://12345.fs1.hubspotusercontent-na1.net/hubfs/12345/style.css">
        </head>
        </html>
        """
        evidence = detect_html(html)

        files_evidence = [e for e in evidence if e["category"] == "files"]
        assert len(files_evidence) >= 1, "Should detect files CDN"

        # Files should be moderate confidence (files ≠ CMS hosting)
        for e in files_evidence:
            assert e["confidence"] == "moderate", f"Files should be moderate, got {e['confidence']}"

    def test_hubfs_path_moderate_confidence(self):
        """Files in /hubfs/ path should be moderate confidence."""
        html = """
        <html>
        <head>
            <link rel="stylesheet" href="/hubfs/12345/style.css">
        </head>
        </html>
        """
        evidence = detect_html(html)

        files_evidence = [e for e in evidence if e["category"] == "files" and "hubfs" in e["patternId"]]
        assert len(files_evidence) >= 1, "Should detect /hubfs/ path"
        assert files_evidence[0]["confidence"] == "moderate"

    def test_cms_network_detection(self):
        """Network requests to hs-sites.com should indicate CMS."""
        network = ["https://12345.hs-sites.com/some-page"]
        evidence = detect_network("\n".join(network))

        cms_evidence = [e for e in evidence if e["category"] == "cms"]
        assert len(cms_evidence) >= 1, "Should detect CMS from network"
        assert cms_evidence[0]["source"] == "url"
        assert cms_evidence[0]["confidence"] == "strong"

    def test_no_cms_on_clean_html(self, sample_html_no_hubspot):
        """HTML without HubSpot should have no CMS evidence."""
        evidence = detect_html(sample_html_no_hubspot)

        cms_evidence = [e for e in evidence if e["category"] == "cms"]
        assert len(cms_evidence) == 0, "Should not detect CMS on clean HTML"

    def test_cms_evidence_has_actual_match_text(self, sample_html_cms_meta):
        """CMS evidence should contain actual matched text, not placeholders."""
        evidence = detect_html(sample_html_cms_meta)

        cms_evidence = [e for e in evidence if e["category"] == "cms"]
        for e in cms_evidence:
            assert e["match"], "Match text should not be empty"
            assert len(e["match"]) > 0, "Match should have content"
            # Should not be hardcoded placeholder
            assert e["match"] != "cms_evidence", "Should not be placeholder"
            assert e["match"] != "generator/hs_cos_wrapper", "Should not be old hardcoded text"
