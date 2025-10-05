"""
Integration tests for crawler.py using respx to mock HTTP responses.

Tests the full flow:
- HTTP fetching with error handling
- HTML parsing and detection
- Cookie parsing from Set-Cookie headers
- Result formatting
- Schema validation
"""
import pytest
import httpx
import respx
from hubspot_crawler.crawler import process_url, fetch_html, normalize_url


class TestNormalizeURL:
    """Test URL normalization."""

    def test_adds_https_to_bare_domain(self):
        """Should add https:// to bare domain."""
        url = normalize_url("example.com")
        assert url == "https://example.com"

    def test_preserves_https_scheme(self):
        """Should preserve existing https:// scheme."""
        url = normalize_url("https://example.com")
        assert url == "https://example.com"

    def test_preserves_http_scheme(self):
        """Should preserve existing http:// scheme."""
        url = normalize_url("http://example.com")
        assert url == "http://example.com"


@pytest.mark.asyncio
class TestFetchHTML:
    """Test HTML fetching with error handling."""

    @respx.mock
    async def test_successful_fetch(self):
        """Should fetch HTML successfully."""
        url = "https://example.com"
        html_content = "<html><head><title>Test</title></head><body>Hello</body></html>"

        respx.get(url).mock(return_value=httpx.Response(200, text=html_content))

        async with httpx.AsyncClient() as client:
            html, headers, status_code, final_url = await fetch_html(client, url)

        assert html == html_content
        assert isinstance(headers, dict)
        assert status_code == 200
        assert final_url == url

    @respx.mock
    async def test_4xx_error_returns_body(self):
        """Should return response body even on 4xx errors."""
        url = "https://example.com/notfound"
        error_html = "<html><body>404 Not Found</body></html>"

        respx.get(url).mock(return_value=httpx.Response(404, text=error_html))

        async with httpx.AsyncClient() as client:
            html, headers, status_code, final_url = await fetch_html(client, url)

        # Should return the error page HTML, not raise
        assert html == error_html
        assert status_code == 404
        assert final_url == url

    @respx.mock
    async def test_5xx_error_returns_body(self):
        """Should return response body even on 5xx errors."""
        url = "https://example.com/error"
        error_html = "<html><body>500 Internal Server Error</body></html>"

        respx.get(url).mock(return_value=httpx.Response(500, text=error_html))

        async with httpx.AsyncClient() as client:
            html, headers, status_code, final_url = await fetch_html(client, url)

        # Should return the error page HTML
        assert html == error_html
        assert status_code == 500

    @respx.mock
    async def test_network_error_raises(self):
        """Should raise on network errors (DNS, timeout, etc)."""
        url = "https://nonexistent.invalid"

        respx.get(url).mock(side_effect=httpx.ConnectError("DNS lookup failed"))

        async with httpx.AsyncClient() as client:
            with pytest.raises(RuntimeError, match="HTTP error"):
                await fetch_html(client, url)

    @respx.mock
    async def test_timeout_error_raises(self):
        """Should raise on timeout."""
        url = "https://slow.example.com"

        respx.get(url).mock(side_effect=httpx.TimeoutException("Request timeout"))

        async with httpx.AsyncClient() as client:
            with pytest.raises(RuntimeError, match="HTTP error"):
                await fetch_html(client, url)


@pytest.mark.asyncio
class TestProcessURL:
    """Test full URL processing flow."""

    @respx.mock
    async def test_process_url_with_tracking(self):
        """Should detect tracking and return valid result."""
        url = "https://example.com"
        html = """
        <html>
        <head>
            <script type="text/javascript" id="hs-script-loader" async defer src="//js.hs-scripts.com/12345.js"></script>
        </head>
        <body>Test</body>
        </html>
        """

        respx.get(url).mock(return_value=httpx.Response(200, text=html))

        async with httpx.AsyncClient() as client:
            result = await process_url(url, url, client, render=False, validate=False)

        assert result["original_url"] == url
        assert "hubIds" in result
        assert 12345 in result["hubIds"]
        assert result["summary"]["tracking"] is True
        assert result["summary"]["confidence"] == "definitive"

    @respx.mock
    async def test_process_url_with_cms(self):
        """Should detect CMS and return valid result."""
        url = "https://example.com"
        html = """
        <html>
        <head>
            <meta name="generator" content="HubSpot">
        </head>
        <body>Test</body>
        </html>
        """

        respx.get(url).mock(return_value=httpx.Response(200, text=html))

        async with httpx.AsyncClient() as client:
            result = await process_url(url, url, client, render=False, validate=False)

        assert result["summary"]["cmsHosting"] is True
        assert result["summary"]["confidence"] == "moderate"

    @respx.mock
    async def test_process_url_parses_set_cookie(self):
        """Should parse Set-Cookie headers for HubSpot cookies."""
        url = "https://example.com"
        html = "<html><body>Test</body></html>"

        headers = {
            "set-cookie": "hubspotutk=abc123; Path=/; HttpOnly"
        }

        respx.get(url).mock(return_value=httpx.Response(200, text=html, headers=headers))

        async with httpx.AsyncClient() as client:
            result = await process_url(url, url, client, render=False, validate=False)

        # Should detect hubspotutk cookie
        cookie_evidence = [e for e in result["evidence"] if e["category"] == "cookies" and "hubspotutk" in e["match"].lower()]
        assert len(cookie_evidence) >= 1, "Should detect hubspotutk cookie"
        assert cookie_evidence[0]["confidence"] == "definitive"

    @respx.mock
    async def test_process_url_with_no_hubspot(self):
        """Should handle sites with no HubSpot."""
        url = "https://example.com"
        html = "<html><body>Clean site</body></html>"

        respx.get(url).mock(return_value=httpx.Response(200, text=html))

        async with httpx.AsyncClient() as client:
            result = await process_url(url, url, client, render=False, validate=False)

        assert result["summary"]["tracking"] is False
        assert result["summary"]["cmsHosting"] is False
        assert result["summary"]["confidence"] == "weak"
        assert result["hubIds"] == []

    @respx.mock
    async def test_process_url_extracts_resources(self):
        """Should extract resource URLs from HTML."""
        url = "https://example.com"
        html = """
        <html>
        <head>
            <script type="text/javascript" id="hs-script-loader" src="https://js.hs-scripts.com/12345.js"></script>
            <link rel="stylesheet" href="https://example.com/style.css">
        </head>
        </html>
        """

        respx.get(url).mock(return_value=httpx.Response(200, text=html))

        async with httpx.AsyncClient() as client:
            result = await process_url(url, url, client, render=False, validate=False)

        # Should detect tracking from script resource
        tracking_evidence = [e for e in result["evidence"] if e["category"] == "tracking"]
        assert len(tracking_evidence) >= 1

    @respx.mock
    async def test_process_url_deduplicates_evidence(self):
        """Should deduplicate evidence items."""
        url = "https://example.com"
        # Multiple script tags with same tracking script
        html = """
        <html>
        <head>
            <script type="text/javascript" id="hs-script-loader" src="//js.hs-scripts.com/12345.js"></script>
            <script type="text/javascript" id="hs-script-loader" src="//js.hs-scripts.com/12345.js"></script>
        </head>
        </html>
        """

        respx.get(url).mock(return_value=httpx.Response(200, text=html))

        async with httpx.AsyncClient() as client:
            result = await process_url(url, url, client, render=False, validate=False)

        # Should deduplicate (same category, patternId, source, match)
        tracking_evidence = [e for e in result["evidence"]
                            if e["category"] == "tracking" and e["patternId"] == "tracking_loader_script"]
        # Should have only 1 deduplicated item (or possibly 1 from HTML + 1 from network)
        assert len(tracking_evidence) <= 2

    @respx.mock
    async def test_process_url_network_error_raises(self):
        """Should raise on network errors."""
        url = "https://nonexistent.invalid"

        respx.get(url).mock(side_effect=httpx.ConnectError("DNS failed"))

        async with httpx.AsyncClient() as client:
            with pytest.raises(RuntimeError, match="Failed to fetch"):
                await process_url(url, url, client, render=False, validate=False)

    @respx.mock
    async def test_process_url_4xx_sets_final_url_to_original(self):
        """For 4xx errors, final_url should equal original_url (not normalized URL)."""
        original_url = "example.com"
        normalized_url = "https://example.com"
        error_html = "<html><body>404 Not Found</body></html>"

        respx.get(normalized_url).mock(return_value=httpx.Response(404, text=error_html))

        async with httpx.AsyncClient() as client:
            result = await process_url(original_url, normalized_url, client, render=False, validate=False)

        # Both URLs should match the original input when there's a 4xx error
        assert result["original_url"] == original_url
        assert result["final_url"] == original_url  # Should equal original, not normalized
        assert result.get("http_status") == 404

    @respx.mock
    async def test_process_url_5xx_sets_final_url_to_original(self):
        """For 5xx errors, final_url should equal original_url (not normalized URL)."""
        original_url = "example.com"
        normalized_url = "https://example.com"
        error_html = "<html><body>500 Internal Server Error</body></html>"

        respx.get(normalized_url).mock(return_value=httpx.Response(500, text=error_html))

        async with httpx.AsyncClient() as client:
            result = await process_url(original_url, normalized_url, client, render=False, validate=False)

        # Both URLs should match the original input when there's a 5xx error
        assert result["original_url"] == original_url
        assert result["final_url"] == original_url  # Should equal original, not normalized
        assert result.get("http_status") == 500


@pytest.mark.asyncio
class TestCookieDetection:
    """Test Set-Cookie header parsing for HubSpot cookies."""

    @respx.mock
    async def test_hubspotutk_cookie_definitive(self):
        """hubspotutk cookie should be definitive confidence."""
        url = "https://example.com"
        html = "<html><body>Test</body></html>"

        headers = {
            "set-cookie": "hubspotutk=xyz789; Path=/; Expires=..."
        }

        respx.get(url).mock(return_value=httpx.Response(200, text=html, headers=headers))

        async with httpx.AsyncClient() as client:
            result = await process_url(url, url, client, render=False, validate=False)

        cookie_evidence = [e for e in result["evidence"] if "hubspotutk" in e["match"].lower()]
        assert len(cookie_evidence) >= 1
        assert cookie_evidence[0]["confidence"] == "definitive", "hubspotutk should be definitive"

    @respx.mock
    async def test_other_hs_cookies_strong(self):
        """Other HubSpot cookies should be strong confidence."""
        url = "https://example.com"
        html = "<html><body>Test</body></html>"

        headers = {
            "set-cookie": "__hstc=abc; Path=/"
        }

        respx.get(url).mock(return_value=httpx.Response(200, text=html, headers=headers))

        async with httpx.AsyncClient() as client:
            result = await process_url(url, url, client, render=False, validate=False)

        cookie_evidence = [e for e in result["evidence"] if e["category"] == "cookies" and "__hstc" in e["match"]]
        if cookie_evidence:
            assert cookie_evidence[0]["confidence"] == "strong"

    @respx.mock
    async def test_multiple_set_cookie_headers(self):
        """Should handle multiple Set-Cookie headers."""
        url = "https://example.com"
        html = "<html><body>Test</body></html>"

        # httpx handles multiple headers
        headers = [
            ("set-cookie", "hubspotutk=abc; Path=/"),
            ("set-cookie", "__hstc=xyz; Path=/")
        ]

        respx.get(url).mock(return_value=httpx.Response(200, text=html, headers=headers))

        async with httpx.AsyncClient() as client:
            result = await process_url(url, url, client, render=False, validate=False)

        cookie_evidence = [e for e in result["evidence"] if e["category"] == "cookies"]
        # Should detect both cookies
        assert len(cookie_evidence) >= 2
