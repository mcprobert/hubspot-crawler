"""
Unit tests for forms detection in detector.py

Tests the specification requirements:
- Forms requires BOTH loader AND create call for definitive confidence
- Loader only = strong confidence
- Forms submissions in network = definitive
"""
import pytest
from hubspot_crawler.detector import detect_html, detect_network


class TestFormsDetection:
    """Test HubSpot forms detection logic."""

    def test_forms_both_loader_and_create_definitive(self, sample_html_forms_complete):
        """Forms with BOTH loader AND create call should be definitive."""
        evidence = detect_html(sample_html_forms_complete)

        forms_evidence = [e for e in evidence if e["category"] == "forms"]
        assert len(forms_evidence) >= 2, "Should have both loader and create call evidence"

        # Loader with create call present should be definitive
        loader_ev = [e for e in forms_evidence if e["patternId"] == "forms_v2_loader"]
        assert len(loader_ev) == 1, "Should have loader evidence"
        assert loader_ev[0]["confidence"] == "definitive", "Loader should be definitive when create call present"

        # Create call should always be definitive
        create_ev = [e for e in forms_evidence if e["patternId"] == "forms_create_call"]
        assert len(create_ev) == 1, "Should have create call evidence"
        assert create_ev[0]["confidence"] == "definitive"

    def test_forms_loader_only_strong(self, sample_html_forms_loader_only):
        """Forms loader without create call should be strong (not definitive)."""
        evidence = detect_html(sample_html_forms_loader_only)

        forms_evidence = [e for e in evidence if e["category"] == "forms"]
        loader_ev = [e for e in forms_evidence if e["patternId"] == "forms_v2_loader"]

        assert len(loader_ev) == 1, "Should have loader evidence"
        # Without create call, should be strong not definitive
        assert loader_ev[0]["confidence"] == "strong", "Loader without create should be strong"

    def test_forms_network_submission_definitive(self, sample_network_forms):
        """Forms submission in network requests should be definitive."""
        evidence = detect_network("\n".join(sample_network_forms))

        forms_evidence = [e for e in evidence if e["category"] == "forms"]
        assert len(forms_evidence) >= 1, "Should detect forms from network"

        # Network submissions are actual form posts = definitive
        for e in forms_evidence:
            if "submit" in e["patternId"]:
                assert e["confidence"] == "definitive", "Network form submissions should be definitive"
                assert e["source"] == "url"

    def test_forms_evidence_has_actual_match(self, sample_html_forms_complete):
        """Forms evidence should contain actual script tags, not placeholders."""
        evidence = detect_html(sample_html_forms_complete)

        forms_evidence = [e for e in evidence if e["category"] == "forms"]
        for e in forms_evidence:
            assert e["match"], "Match should not be empty"
            # Should not be old hardcoded placeholder (Bug #7)
            assert e["match"] != "v2.js + hbspt.forms.create", "Should not be hardcoded text"
            # Should contain actual code
            assert "hsforms" in e["match"] or "hbspt" in e["match"] or "forms" in e["match"]

    def test_forms_hidden_context_strong(self):
        """Hidden hs_context field should be strong evidence."""
        html = """
        <html>
        <body>
            <form>
                <input type="hidden" name="hs_context" value='{"formId":"abc"}'>
            </form>
        </body>
        </html>
        """
        evidence = detect_html(html)

        forms_evidence = [e for e in evidence if e["patternId"] == "forms_hidden_hs_context"]
        if forms_evidence:
            assert forms_evidence[0]["confidence"] == "strong"
            assert forms_evidence[0]["category"] == "forms"

    def test_no_forms_on_clean_html(self, sample_html_no_hubspot):
        """HTML without HubSpot should have no forms evidence."""
        evidence = detect_html(sample_html_no_hubspot)

        forms_evidence = [e for e in evidence if e["category"] == "forms"]
        assert len(forms_evidence) == 0, "Should not detect forms on clean HTML"

    def test_forms_loader_match_contains_script_tag(self, sample_html_forms_complete):
        """Forms loader evidence should contain the actual script src."""
        evidence = detect_html(sample_html_forms_complete)

        loader_ev = [e for e in evidence if e["patternId"] == "forms_v2_loader"]
        assert len(loader_ev) == 1
        assert "hsforms.net" in loader_ev[0]["match"] or "v2.js" in loader_ev[0]["match"]

    def test_forms_create_match_contains_code(self, sample_html_forms_complete):
        """Forms create call evidence should contain actual hbspt.forms.create code."""
        evidence = detect_html(sample_html_forms_complete)

        create_ev = [e for e in evidence if e["patternId"] == "forms_create_call"]
        assert len(create_ev) == 1
        assert "hbspt.forms.create" in create_ev[0]["match"]
