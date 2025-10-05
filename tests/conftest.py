"""
Pytest configuration and shared fixtures for HubSpot crawler tests.
"""
import pytest
from pathlib import Path


@pytest.fixture
def fixtures_dir():
    """Return path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_html_with_tracking(fixtures_dir):
    """Sample HTML with HubSpot tracking script."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Test Page</title>
        <script type="text/javascript" id="hs-script-loader" async defer src="//js.hs-scripts.com/12345.js"></script>
    </head>
    <body>
        <h1>Test Page</h1>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_cms_meta(fixtures_dir):
    """Sample HTML with CMS meta generator tag."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="generator" content="HubSpot">
        <title>CMS Page</title>
    </head>
    <body>
        <h1>CMS Page</h1>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_cms_wrapper_with_hcms(fixtures_dir):
    """Sample HTML with wrapper class AND /_hcms/ path."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>CMS Page</title>
        <link rel="stylesheet" href="/_hcms/style.css">
    </head>
    <body>
        <div class="hs_cos_wrapper">
            <h1>CMS Content</h1>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_cms_wrapper_no_hcms(fixtures_dir):
    """Sample HTML with wrapper class but NO /_hcms/ path (should NOT be CMS)."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Page</title>
    </head>
    <body>
        <div class="hs_cos_wrapper">
            <h1>Content</h1>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_forms_complete(fixtures_dir):
    """Sample HTML with BOTH forms loader AND create call (definitive)."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <script charset="utf-8" type="text/javascript" src="//js.hsforms.net/forms/v2.js"></script>
        <script>
            hbspt.forms.create({
                portalId: "12345",
                formId: "12345678-1234-5678-1234-567812345678"
            });
        </script>
    </head>
    <body>
        <h1>Form Page</h1>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_forms_loader_only(fixtures_dir):
    """Sample HTML with forms loader but NO create call (strong, not definitive)."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <script charset="utf-8" type="text/javascript" src="//js.hsforms.net/forms/v2.js"></script>
    </head>
    <body>
        <h1>Page</h1>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_cta_complete(fixtures_dir):
    """Sample HTML with BOTH CTA loader AND load call (definitive)."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <script charset="utf-8" src="https://js.hscta.net/cta/current.js"></script>
        <script type="text/javascript">
            hbspt.cta.load(12345, '12345678-1234-5678-1234-567812345678');
        </script>
    </head>
    <body>
        <h1>CTA Page</h1>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_video(fixtures_dir):
    """Sample HTML with HubSpot video embed."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Video Page</title>
    </head>
    <body>
        <iframe src="https://play.hubspotvideo.com/12345"></iframe>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_chat(fixtures_dir):
    """Sample HTML with HubSpot chat/conversations."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <script type="text/javascript" src="//js.usemessages.com/conversations-embed.js"></script>
    </head>
    <body>
        <h1>Chat Page</h1>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_analytics(fixtures_dir):
    """Sample HTML with HubSpot analytics script with Hub ID."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <script type="text/javascript" src="//js.hs-analytics.net/analytics/1234567890/67890.js"></script>
    </head>
    <body>
        <h1>Analytics Page</h1>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_no_hubspot(fixtures_dir):
    """Sample HTML with no HubSpot at all."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Clean Page</title>
        <script src="https://example.com/script.js"></script>
    </head>
    <body>
        <h1>No HubSpot Here</h1>
    </body>
    </html>
    """


@pytest.fixture
def sample_network_tracking():
    """Sample network requests with tracking scripts."""
    return [
        "https://js.hs-scripts.com/12345.js",
        "https://js.hs-analytics.net/analytics/1234567890/67890.js"
    ]


@pytest.fixture
def sample_network_forms():
    """Sample network requests with forms submissions."""
    return [
        "https://api.hsforms.com/submissions/v3/integration/submit/12345/12345678-1234-5678-1234-567812345678"
    ]


@pytest.fixture
def sample_network_chat():
    """Sample network requests with chat API calls."""
    return [
        "https://api.usemessages.com/v1/conversations"
    ]


@pytest.fixture
def sample_headers_with_hubspot():
    """Sample HTTP headers indicating HubSpot (Hub ID in headers)."""
    return {
        "x-hs-hub-id": "12345",
        "x-hs-portal-id": "12345",
        "set-cookie": "hubspotutk=abc123; Path=/; Expires=...",
        "server": "HubSpot"
    }


@pytest.fixture
def sample_headers_no_hubspot():
    """Sample HTTP headers without HubSpot."""
    return {
        "server": "nginx",
        "content-type": "text/html; charset=utf-8"
    }


@pytest.fixture
def sample_html_hsq_queue(fixtures_dir):
    """HTML with _hsq analytics queue initialization."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <script type="text/javascript">
            window._hsq = window._hsq || [];
            _hsq.push(['setPath', '/homepage']);
            _hsq.push(['trackPageView']);
        </script>
    </head>
    <body>
        <h1>Page with Analytics Queue</h1>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_url_params(fixtures_dir):
    """HTML with HubSpot URL tracking parameters."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <link rel="canonical" href="https://example.com/page?_hsmi=12345&_hsenc=p2ANqtz-abc">
        <meta property="og:url" content="https://example.com/page?_hsfp=987654">
    </head>
    <body>
        <h1>Page with URL Params</h1>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_banner_helper(fixtures_dir):
    """HTML with HubSpot banner helper script."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <script type="text/javascript" src="https://js.hs-banner.com/12345.js"></script>
    </head>
    <body>
        <h1>Page with Banner</h1>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_tracking_no_id(fixtures_dir):
    """Tracking script without id attribute (fallback pattern)."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <script type="text/javascript" src="//js.hs-scripts.com/54321.js"></script>
    </head>
    <body>
        <h1>Page with Tracking No ID</h1>
    </body>
    </html>
    """
