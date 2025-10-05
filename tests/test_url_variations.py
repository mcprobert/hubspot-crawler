"""
Tests for URL variation generation and fallback logic
"""
import pytest
from hubspot_crawler.crawler import generate_url_variations


class TestGenerateUrlVariations:
    """Test URL variation generation"""

    def test_basic_www_addition(self):
        """Test adding www to URL without it"""
        url = "https://example.com"
        variations = generate_url_variations(url)
        assert "https://www.example.com" in variations

    def test_basic_www_removal(self):
        """Test removing www from URL with it"""
        url = "https://www.example.com"
        variations = generate_url_variations(url)
        assert "https://example.com" in variations

    def test_scheme_switching_https_to_http(self):
        """Test switching from https to http"""
        url = "https://example.com"
        variations = generate_url_variations(url)
        assert "http://example.com" in variations

    def test_scheme_switching_http_to_https(self):
        """Test switching from http to https"""
        url = "http://example.com"
        variations = generate_url_variations(url)
        assert "https://example.com" in variations

    def test_trailing_slash_addition(self):
        """Test adding trailing slash when not present"""
        url = "https://example.com/page"
        variations = generate_url_variations(url)
        assert "https://example.com/page/" in variations

    def test_trailing_slash_removal(self):
        """Test removing trailing slash when present"""
        url = "https://example.com/page/"
        variations = generate_url_variations(url)
        assert "https://example.com/page" in variations

    def test_trailing_slash_not_removed_from_root(self):
        """Test that trailing slash is not removed from root path"""
        url = "https://example.com/"
        variations = generate_url_variations(url)
        # Should not contain "https://example.com" (root slash should stay)
        # But should contain www variation
        assert "https://www.example.com/" in variations

    def test_no_duplicates(self):
        """Test that variations don't contain duplicates"""
        url = "https://example.com"
        variations = generate_url_variations(url)
        assert len(variations) == len(set(variations))

    def test_original_url_not_in_variations(self):
        """Test that original URL is not included in variations"""
        url = "https://example.com"
        variations = generate_url_variations(url)
        assert url not in variations

    def test_max_variations_limit(self):
        """Test that max_variations parameter limits output"""
        url = "https://example.com/page"
        variations = generate_url_variations(url, max_variations=2)
        assert len(variations) <= 2

    def test_max_variations_zero(self):
        """Test that max_variations=0 returns empty list"""
        url = "https://example.com"
        variations = generate_url_variations(url, max_variations=0)
        assert variations == []

    def test_complex_url_with_query_params(self):
        """Test variations preserve query parameters"""
        url = "https://example.com/page?foo=bar&baz=qux"
        variations = generate_url_variations(url)
        # Check that query params are preserved
        for variation in variations:
            assert "foo=bar" in variation
            assert "baz=qux" in variation

    def test_complex_url_with_fragment(self):
        """Test variations preserve URL fragments"""
        url = "https://example.com/page#section"
        variations = generate_url_variations(url)
        # Check that fragment is preserved
        for variation in variations:
            assert "#section" in variation

    def test_url_with_port(self):
        """Test variations preserve port number"""
        url = "https://example.com:8080/page"
        variations = generate_url_variations(url)
        # Check that port is preserved
        for variation in variations:
            assert ":8080" in variation

    def test_url_with_path(self):
        """Test variations with complex path"""
        url = "https://example.com/path/to/page"
        variations = generate_url_variations(url)
        # Check that path is preserved
        for variation in variations:
            assert "/path/to/page" in variation

    def test_subdomain_not_treated_as_www(self):
        """Test that subdomains other than www are preserved"""
        url = "https://blog.example.com"
        variations = generate_url_variations(url)
        # Should add www to existing subdomain
        assert "https://www.blog.example.com" in variations
        # Should not remove blog subdomain
        assert not any(v == "https://example.com" for v in variations)

    def test_multiple_subdomains(self):
        """Test URL with multiple subdomains"""
        url = "https://api.staging.example.com"
        variations = generate_url_variations(url)
        # Should add www prefix
        assert "https://www.api.staging.example.com" in variations

    def test_www_subdomain_removal_only_removes_www(self):
        """Test that www removal only removes www, not other parts"""
        url = "https://www.example.com"
        variations = generate_url_variations(url)
        assert "https://example.com" in variations
        # Should not create malformed URLs
        for variation in variations:
            assert variation.count("://") == 1

    def test_all_variation_types_generated(self):
        """Test that all 4 variation types are attempted"""
        url = "https://example.com/page"
        variations = generate_url_variations(url, max_variations=4)

        # Should have up to 4 unique variations (some might overlap)
        assert len(variations) >= 2  # At minimum www and scheme

        # Check that we have variety
        has_www_change = any("www." in v for v in variations)
        has_scheme_change = any("http://" in v for v in variations)
        assert has_www_change or has_scheme_change

    def test_priority_order_www_first(self):
        """Test that www variation comes first"""
        url = "https://example.com"
        variations = generate_url_variations(url, max_variations=4)
        # First variation should be www-related
        assert variations[0] == "https://www.example.com"

    def test_priority_order_scheme_second(self):
        """Test that scheme variation comes second"""
        url = "https://example.com"
        variations = generate_url_variations(url, max_variations=4)
        # Second variation should be scheme change
        assert variations[1] == "http://example.com"


class TestUrlVariationEdgeCases:
    """Test edge cases for URL variation generation"""

    def test_empty_path(self):
        """Test URL with no path"""
        url = "https://example.com"
        variations = generate_url_variations(url)
        assert len(variations) > 0
        # Should include trailing slash variant
        assert "https://example.com/" in variations

    def test_ip_address_url(self):
        """Test URL with IP address"""
        url = "https://192.168.1.1"
        variations = generate_url_variations(url)
        # Should handle IP addresses gracefully
        assert len(variations) > 0
        # www on IP is unusual but valid
        assert "https://www.192.168.1.1" in variations

    def test_localhost_url(self):
        """Test localhost URL"""
        url = "http://localhost:3000"
        variations = generate_url_variations(url)
        # Should handle localhost
        assert "https://localhost:3000" in variations
        assert "http://www.localhost:3000" in variations

    def test_url_with_auth(self):
        """Test URL with authentication"""
        url = "https://user:pass@example.com/page"
        variations = generate_url_variations(url)
        # Should preserve auth
        for variation in variations:
            assert "user:pass@" in variation

    def test_very_long_url(self):
        """Test that very long URLs don't cause issues"""
        path = "/" + "a" * 1000
        url = f"https://example.com{path}"
        variations = generate_url_variations(url)
        # Should handle long URLs
        assert len(variations) > 0
        for variation in variations:
            assert path in variation
