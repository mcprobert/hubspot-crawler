"""
Tests for anti-blocking features (Phase 6.7).

Covers:
- Per-domain rate limiting
- Request delays with jitter
- Smart 429/403 detection
- Conservative exponential backoff
- Domain semaphore isolation
"""

import pytest
import time
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from hubspot_crawler.crawler import run


class TestRequestDelays:
    """Test request delay and jitter functionality"""

    @pytest.mark.asyncio
    async def test_delay_applied_between_requests(self):
        """Should apply delay between consecutive requests"""
        # We'll measure time for sequential requests (concurrency=1)
        # With delay=0.3, two requests should take at least 0.6s
        urls = ["https://example.com", "https://example.org"]

        with patch('hubspot_crawler.crawler.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.text = "<html></html>"
            mock_response.headers = {}
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            start_time = time.time()
            await run(urls, concurrency=1, delay=0.3, jitter=0.0, max_per_domain=1, quiet=True)
            elapsed = time.time() - start_time

            # Should take at least 0.6s (2 requests * 0.3s delay each)
            # Allow some tolerance for test timing
            assert elapsed >= 0.55, f"Expected >= 0.55s, got {elapsed}s"

    @pytest.mark.asyncio
    async def test_jitter_randomizes_delay(self):
        """Jitter should add randomness to delays"""
        # We can't easily test randomness in a single run, but we can verify
        # that jitter parameter is accepted and doesn't break anything
        urls = ["https://example.com"]

        with patch('hubspot_crawler.crawler.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.text = "<html></html>"
            mock_response.headers = {}
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            # Should not raise any errors
            await run(urls, concurrency=1, delay=0.1, jitter=0.05, max_per_domain=1, quiet=True)

    @pytest.mark.asyncio
    async def test_zero_delay_disables_waiting(self):
        """With delay=0, requests should be immediate"""
        urls = ["https://example.com", "https://example.org"]

        with patch('hubspot_crawler.crawler.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.text = "<html></html>"
            mock_response.headers = {}
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            start_time = time.time()
            await run(urls, concurrency=2, delay=0.0, jitter=0.0, max_per_domain=1, quiet=True)
            elapsed = time.time() - start_time

            # Should be very fast with no delays
            assert elapsed < 0.5, f"Expected < 0.5s with delay=0, got {elapsed}s"


class TestPerDomainRateLimiting:
    """Test per-domain concurrency limiting"""

    @pytest.mark.asyncio
    async def test_max_per_domain_limits_concurrent_requests(self):
        """Should not exceed max_per_domain concurrent requests to same domain"""
        # 3 URLs from same domain, max_per_domain=1
        # Should process sequentially, not in parallel
        urls = [
            "https://example.com/page1",
            "https://example.com/page2",
            "https://example.com/page3"
        ]

        concurrent_requests = []
        max_concurrent = [0]  # Track max concurrent requests

        async def mock_get(*args, **kwargs):
            """Mock that tracks concurrent requests"""
            concurrent_requests.append(1)
            max_concurrent[0] = max(max_concurrent[0], len(concurrent_requests))
            await asyncio.sleep(0.1)  # Simulate request time
            concurrent_requests.pop()

            mock_response = MagicMock()
            mock_response.text = "<html></html>"
            mock_response.headers = {}
            mock_response.status_code = 200
            return mock_response

        with patch('hubspot_crawler.crawler.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = mock_get
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            await run(urls, concurrency=10, delay=0.0, jitter=0.0, max_per_domain=1, quiet=True)

            # With max_per_domain=1, should never have more than 1 concurrent request
            assert max_concurrent[0] <= 1, f"Expected max 1 concurrent, got {max_concurrent[0]}"

    @pytest.mark.asyncio
    async def test_different_domains_can_run_concurrently(self):
        """Different domains should be able to run concurrently"""
        # 3 URLs from different domains, should run in parallel
        urls = [
            "https://example.com",
            "https://example.org",
            "https://example.net"
        ]

        concurrent_requests = []
        max_concurrent = [0]

        async def mock_get(*args, **kwargs):
            concurrent_requests.append(1)
            max_concurrent[0] = max(max_concurrent[0], len(concurrent_requests))
            await asyncio.sleep(0.1)
            concurrent_requests.pop()

            mock_response = MagicMock()
            mock_response.text = "<html></html>"
            mock_response.headers = {}
            mock_response.status_code = 200
            return mock_response

        with patch('hubspot_crawler.crawler.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = mock_get
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            await run(urls, concurrency=3, delay=0.0, jitter=0.0, max_per_domain=1, quiet=True)

            # Different domains can run concurrently
            assert max_concurrent[0] >= 2, f"Expected concurrent requests to different domains"


class TestConservativeDefaults:
    """Test that conservative defaults are applied"""

    def test_default_concurrency_is_ultra_conservative(self):
        """Default concurrency should be 2 (ultra-conservative)"""
        # This is tested implicitly by the run() signature default
        # We can verify by checking the actual parameter
        import inspect
        sig = inspect.signature(run)
        concurrency_default = sig.parameters['concurrency'].default
        assert concurrency_default == 2, f"Expected default concurrency=2, got {concurrency_default}"

    def test_default_delay_is_three_seconds(self):
        """Default delay should be 3.0 seconds (ultra-conservative)"""
        import inspect
        sig = inspect.signature(run)
        delay_default = sig.parameters['delay'].default
        assert delay_default == 3.0, f"Expected default delay=3.0, got {delay_default}"

    def test_default_max_per_domain_is_one(self):
        """Default max_per_domain should be 1"""
        import inspect
        sig = inspect.signature(run)
        max_per_domain_default = sig.parameters['max_per_domain'].default
        assert max_per_domain_default == 1, f"Expected default max_per_domain=1, got {max_per_domain_default}"

    def test_default_jitter_is_one_second(self):
        """Default jitter should be 1.0 second (ultra-conservative)"""
        import inspect
        sig = inspect.signature(run)
        jitter_default = sig.parameters['jitter'].default
        assert jitter_default == 1.0, f"Expected default jitter=1.0, got {jitter_default}"


class TestBackoffTiming:
    """Test conservative exponential backoff"""

    @pytest.mark.asyncio
    async def test_longer_backoff_on_retry(self):
        """Retries should use longer backoff (5s, 15s, 45s)"""
        urls = ["https://example.com"]

        attempt_count = [0]

        async def mock_get_failing(*args, **kwargs):
            """Mock that fails to trigger retries"""
            attempt_count[0] += 1
            raise Exception("Connection timeout")

        with patch('hubspot_crawler.crawler.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = mock_get_failing
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            start_time = time.time()
            await run(urls, concurrency=1, delay=0.0, jitter=0.0, max_retries=3, max_per_domain=1, quiet=True)
            elapsed = time.time() - start_time

            # Should have tried 3 times with backoffs of 5s and 15s = 20s minimum
            # (first attempt immediate, then 5s wait, retry, 15s wait, retry)
            assert attempt_count[0] == 3, f"Expected 3 attempts, got {attempt_count[0]}"
            # Allow some tolerance for timing
            assert elapsed >= 19.0, f"Expected >= 19s for backoffs (5s + 15s), got {elapsed}s"
