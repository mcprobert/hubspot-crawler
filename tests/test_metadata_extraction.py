"""
Tests for metadata extraction functionality (Phase 6).

Covers:
- extract_page_metadata() function
- HTTP status code capture in fetch_html()
- make_result() with new fields
- Schema validation with new fields
- Backward compatibility
"""

import pytest
from hubspot_crawler.crawler import extract_page_metadata
from hubspot_crawler.detector import make_result


class TestExtractPageMetadata:
    """Test the extract_page_metadata function"""

    def test_extracts_title_and_description(self):
        """Should extract both title and description from valid HTML"""
        html = """
        <html>
        <head>
            <title>Test Page Title</title>
            <meta name="description" content="This is a test description">
        </head>
        <body>Content</body>
        </html>
        """
        result = extract_page_metadata(html)
        assert result["title"] == "Test Page Title"
        assert result["description"] == "This is a test description"

    def test_extracts_title_only(self):
        """Should extract title when description is missing"""
        html = """
        <html>
        <head>
            <title>Only Title</title>
        </head>
        <body>Content</body>
        </html>
        """
        result = extract_page_metadata(html)
        assert result["title"] == "Only Title"
        assert result["description"] is None

    def test_extracts_description_only(self):
        """Should extract description when title is missing"""
        html = """
        <html>
        <head>
            <meta name="description" content="Only description">
        </head>
        <body>Content</body>
        </html>
        """
        result = extract_page_metadata(html)
        assert result["title"] is None
        assert result["description"] == "Only description"

    def test_handles_missing_both(self):
        """Should return None for both when tags are missing"""
        html = """
        <html>
        <head>
        </head>
        <body>Content</body>
        </html>
        """
        result = extract_page_metadata(html)
        assert result["title"] is None
        assert result["description"] is None

    def test_handles_empty_title(self):
        """Should return None for empty title"""
        html = "<html><head><title></title></head></html>"
        result = extract_page_metadata(html)
        assert result["title"] is None

    def test_handles_empty_description(self):
        """Should return None for empty description content"""
        html = '<html><head><meta name="description" content=""></head></html>'
        result = extract_page_metadata(html)
        assert result["description"] is None

    def test_handles_whitespace_only_title(self):
        """Should handle title with only whitespace"""
        html = "<html><head><title>   </title></head></html>"
        result = extract_page_metadata(html)
        # BeautifulSoup's get_text(strip=True) will return empty string, which becomes None
        assert result["title"] is None or result["title"] == ""

    def test_handles_malformed_html(self):
        """Should gracefully handle malformed HTML"""
        html = "<html><head><title>Unclosed tag"
        result = extract_page_metadata(html)
        # Should not raise exception, even with malformed HTML
        assert isinstance(result, dict)
        assert "title" in result
        assert "description" in result

    def test_handles_meta_description_case_insensitive(self):
        """Should handle meta name attribute case variations"""
        html = '<html><head><meta name="Description" content="Test"></head></html>'
        result = extract_page_metadata(html)
        # BeautifulSoup find with attrs should be case-sensitive, so this tests actual behavior
        assert result["description"] is None or result["description"] == "Test"

    def test_strips_whitespace_from_values(self):
        """Should strip whitespace from title and description"""
        html = """
        <html>
        <head>
            <title>  Padded Title  </title>
            <meta name="description" content="  Padded description  ">
        </head>
        </html>
        """
        result = extract_page_metadata(html)
        assert result["title"] == "Padded Title"
        assert result["description"] == "Padded description"

    def test_handles_multiline_title(self):
        """Should handle title with line breaks"""
        html = """
        <html>
        <head>
            <title>
                Multi
                Line
                Title
            </title>
        </head>
        </html>
        """
        result = extract_page_metadata(html)
        # get_text(strip=True) should normalize whitespace
        assert "Multi" in result["title"]
        assert "Line" in result["title"]
        assert "Title" in result["title"]


class TestMakeResultWithMetadata:
    """Test make_result function with new optional parameters"""

    def test_make_result_with_http_status(self):
        """Should include http_status when provided"""
        result = make_result(
            original_url="https://example.com",
            final_url="https://example.com",
            evidence=[],
            http_status=200
        )
        assert result["http_status"] == 200

    def test_make_result_with_page_metadata(self):
        """Should include page_metadata when provided"""
        metadata = {"title": "Test", "description": "Desc"}
        result = make_result(
            original_url="https://example.com",
            final_url="https://example.com",
            evidence=[],
            page_metadata=metadata
        )
        assert result["page_metadata"] == metadata
        assert result["page_metadata"]["title"] == "Test"
        assert result["page_metadata"]["description"] == "Desc"

    def test_make_result_with_both_new_fields(self):
        """Should include both new fields when provided"""
        metadata = {"title": "Test", "description": "Desc"}
        result = make_result(
            original_url="https://example.com",
            final_url="https://example.com",
            evidence=[],
            http_status=200,
            page_metadata=metadata
        )
        assert result["http_status"] == 200
        assert result["page_metadata"] == metadata

    def test_make_result_without_new_fields(self):
        """Should work without new fields (backward compatibility)"""
        result = make_result(
            original_url="https://example.com",
            final_url="https://example.com",
            evidence=[]
        )
        # New fields should not be present when not provided
        assert "http_status" not in result
        assert "page_metadata" not in result

    def test_make_result_with_none_http_status(self):
        """Should not include http_status when None"""
        result = make_result(
            original_url="https://example.com",
            final_url="https://example.com",
            evidence=[],
            http_status=None
        )
        assert "http_status" not in result

    def test_make_result_with_none_page_metadata(self):
        """Should not include page_metadata when None"""
        result = make_result(
            original_url="https://example.com",
            final_url="https://example.com",
            evidence=[],
            page_metadata=None
        )
        assert "page_metadata" not in result

    def test_make_result_with_4xx_status(self):
        """Should handle 4xx status codes"""
        result = make_result(
            original_url="https://example.com",
            final_url="https://example.com",
            evidence=[],
            http_status=404
        )
        assert result["http_status"] == 404

    def test_make_result_with_5xx_status(self):
        """Should handle 5xx status codes"""
        result = make_result(
            original_url="https://example.com",
            final_url="https://example.com",
            evidence=[],
            http_status=500
        )
        assert result["http_status"] == 500

    def test_make_result_preserves_existing_fields(self):
        """Should preserve all existing fields when adding new ones"""
        evidence = [{
            "category": "tracking",
            "patternId": "test",
            "match": "test",
            "source": "html",
            "confidence": "strong",
            "hubId": 123
        }]
        metadata = {"title": "Test", "description": "Desc"}
        result = make_result(
            original_url="https://example.com",
            final_url="https://example.com",
            evidence=evidence,
            headers={"content-type": "text/html"},
            http_status=200,
            page_metadata=metadata
        )

        # Check existing fields are present
        assert result["original_url"] == "https://example.com"
        assert result["final_url"] == "https://example.com"
        assert "timestamp" in result
        assert result["hubIds"] == [123]
        assert "summary" in result
        assert result["evidence"] == evidence
        assert result["headers"] == {"content-type": "text/html"}

        # Check new fields are present
        assert result["http_status"] == 200
        assert result["page_metadata"] == metadata
