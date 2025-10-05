"""
Tests for block detection functionality.
"""

import pytest
from hubspot_crawler.crawler import BlockDetector
from collections import deque


class TestBlockDetector:
    """Test BlockDetector class logic"""

    def test_initialization(self):
        """Test BlockDetector initializes with correct defaults"""
        detector = BlockDetector(threshold=5, window_size=20)

        assert detector.threshold == 5
        assert detector.window_size == 20
        assert len(detector.recent_attempts) == 0
        assert len(detector.failed_urls_for_retry) == 0

    def test_record_successful_attempt(self):
        """Test recording a successful attempt"""
        detector = BlockDetector(threshold=5, window_size=20)

        detector.record_attempt("https://example.com", success=True, status_code=200)

        assert len(detector.recent_attempts) == 1
        url, domain, is_blocking, timestamp = detector.recent_attempts[0]
        assert url == "https://example.com"
        assert domain == "example.com"
        assert is_blocking is False
        assert len(detector.failed_urls_for_retry) == 0

    def test_record_403_as_blocking(self):
        """Test 403 status code classified as blocking"""
        detector = BlockDetector(threshold=5, window_size=20)

        detector.record_attempt("https://example.com", success=False, status_code=403)

        assert len(detector.recent_attempts) == 1
        url, domain, is_blocking, timestamp = detector.recent_attempts[0]
        assert is_blocking is True
        assert len(detector.failed_urls_for_retry) == 1

    def test_record_429_as_blocking(self):
        """Test 429 status code classified as blocking"""
        detector = BlockDetector(threshold=5, window_size=20)

        detector.record_attempt("https://example.com", success=False, status_code=429)

        assert len(detector.recent_attempts) == 1
        url, domain, is_blocking, timestamp = detector.recent_attempts[0]
        assert is_blocking is True
        assert len(detector.failed_urls_for_retry) == 1

    def test_record_404_not_blocking(self):
        """Test 404 status code not classified as blocking"""
        detector = BlockDetector(threshold=5, window_size=20)

        detector.record_attempt("https://example.com", success=False, status_code=404)

        assert len(detector.recent_attempts) == 1
        url, domain, is_blocking, timestamp = detector.recent_attempts[0]
        assert is_blocking is False
        assert len(detector.failed_urls_for_retry) == 0

    def test_connection_reset_as_blocking(self):
        """Test connection reset exception classified as blocking"""
        detector = BlockDetector(threshold=5, window_size=20)

        exception = Exception("Connection reset by peer")
        detector.record_attempt("https://example.com", success=False, exception=exception)

        assert len(detector.recent_attempts) == 1
        url, domain, is_blocking, timestamp = detector.recent_attempts[0]
        assert is_blocking is True
        assert len(detector.failed_urls_for_retry) == 1

    def test_tls_error_as_blocking(self):
        """Test TLS/SSL errors classified as blocking"""
        detector = BlockDetector(threshold=5, window_size=20)

        exception = Exception("TLS handshake failed")
        detector.record_attempt("https://example.com", success=False, exception=exception)

        assert len(detector.recent_attempts) == 1
        url, domain, is_blocking, timestamp = detector.recent_attempts[0]
        assert is_blocking is True

    def test_timeout_not_blocking(self):
        """Test timeout errors not classified as blocking"""
        detector = BlockDetector(threshold=5, window_size=20)

        exception = Exception("Request timeout")
        detector.record_attempt("https://example.com", success=False, exception=exception)

        assert len(detector.recent_attempts) == 1
        url, domain, is_blocking, timestamp = detector.recent_attempts[0]
        assert is_blocking is False
        assert len(detector.failed_urls_for_retry) == 0

    def test_sliding_window_max_size(self):
        """Test sliding window respects max size"""
        detector = BlockDetector(threshold=5, window_size=10)

        # Add 15 attempts (more than window size)
        for i in range(15):
            detector.record_attempt(f"https://example{i}.com", success=True, status_code=200)

        # Should only keep last 10
        assert len(detector.recent_attempts) == 10

    def test_not_blocked_insufficient_failures(self):
        """Test blocking not triggered with insufficient failures"""
        detector = BlockDetector(threshold=5, window_size=20)

        # Add 4 blocking failures (below threshold of 5)
        for i in range(4):
            detector.record_attempt(f"https://example{i}.com", success=False, status_code=403)

        is_blocked, stats = detector.is_likely_blocked()
        assert is_blocked is False
        assert stats == {}

    def test_not_blocked_single_domain(self):
        """Test blocking not triggered when all failures are same domain"""
        detector = BlockDetector(threshold=5, window_size=20)

        # Add 5 blocking failures from same domain
        for i in range(5):
            detector.record_attempt("https://example.com/page", success=False, status_code=403)

        is_blocked, stats = detector.is_likely_blocked()
        assert is_blocked is False  # Single domain issues don't indicate IP block

    def test_not_blocked_low_rate(self):
        """Test blocking not triggered when blocking rate is low"""
        detector = BlockDetector(threshold=5, window_size=20)

        # Add 5 blocking failures across 2 domains
        detector.record_attempt("https://example1.com", success=False, status_code=403)
        detector.record_attempt("https://example2.com", success=False, status_code=403)
        detector.record_attempt("https://example1.com", success=False, status_code=403)
        detector.record_attempt("https://example2.com", success=False, status_code=403)
        detector.record_attempt("https://example1.com", success=False, status_code=403)

        # Add 10 successful attempts (total 15, blocking rate = 5/15 = 33% < 60%)
        for i in range(10):
            detector.record_attempt(f"https://success{i}.com", success=True, status_code=200)

        is_blocked, stats = detector.is_likely_blocked()
        assert is_blocked is False  # Blocking rate too low

    def test_blocked_multi_domain_high_rate(self):
        """Test blocking triggered with multiple domains and high failure rate"""
        detector = BlockDetector(threshold=5, window_size=20)

        # Add 5 blocking failures across 2 domains
        detector.record_attempt("https://example1.com", success=False, status_code=403)
        detector.record_attempt("https://example2.com", success=False, status_code=429)
        detector.record_attempt("https://example3.com", success=False, status_code=403)
        detector.record_attempt("https://example1.com", success=False, status_code=403)
        detector.record_attempt("https://example2.com", success=False, status_code=403)

        # Add 2 successful attempts (total 7, blocking rate = 5/7 = 71% > 60%)
        detector.record_attempt("https://success1.com", success=True, status_code=200)
        detector.record_attempt("https://success2.com", success=True, status_code=200)

        is_blocked, stats = detector.is_likely_blocked()
        assert is_blocked is True
        assert stats['blocking_failures'] == 5
        assert stats['unique_domains'] >= 2
        assert stats['blocking_rate'] > 0.6

    def test_stats_returned_on_block(self):
        """Test detailed stats returned when blocking detected"""
        detector = BlockDetector(threshold=5, window_size=20)

        # Trigger blocking
        for i in range(5):
            detector.record_attempt(f"https://example{i % 2}.com", success=False, status_code=403)

        is_blocked, stats = detector.is_likely_blocked()

        assert stats['blocking_failures'] == 5
        assert stats['total_attempts'] == 5
        assert stats['blocking_rate'] == 1.0
        assert stats['unique_domains'] == 2
        assert len(stats['affected_domains']) <= 5
        assert stats['retry_queue_size'] == 5

    def test_get_retry_urls(self):
        """Test retrieving failed URLs for retry"""
        detector = BlockDetector(threshold=5, window_size=20)

        # Add some blocking failures
        detector.record_attempt("https://example1.com", success=False, status_code=403)
        detector.record_attempt("https://example2.com", success=False, status_code=429)
        detector.record_attempt("https://example3.com", success=False, status_code=403)

        retry_urls = detector.get_retry_urls()
        assert len(retry_urls) == 3
        assert "https://example1.com" in retry_urls
        assert "https://example2.com" in retry_urls
        assert "https://example3.com" in retry_urls

    def test_reset_clears_attempts(self):
        """Test reset clears recent attempts"""
        detector = BlockDetector(threshold=5, window_size=20)

        # Add some attempts
        for i in range(5):
            detector.record_attempt(f"https://example{i}.com", success=False, status_code=403)

        assert len(detector.recent_attempts) == 5

        detector.reset()

        assert len(detector.recent_attempts) == 0
        # Retry queue should be preserved
        assert len(detector.failed_urls_for_retry) == 5

    def test_retry_queue_max_size(self):
        """Test retry queue respects max size of 50"""
        detector = BlockDetector(threshold=5, window_size=20)

        # Add 60 blocking failures
        for i in range(60):
            detector.record_attempt(f"https://example{i}.com", success=False, status_code=403)

        # Should only keep last 50
        assert len(detector.failed_urls_for_retry) == 50

    def test_affected_domains_limited_to_five(self):
        """Test affected domains in stats limited to 5 for display"""
        detector = BlockDetector(threshold=5, window_size=20)

        # Add blocking failures from 6 different domains
        for i in range(6):
            detector.record_attempt(f"https://example{i}.com", success=False, status_code=403)

        is_blocked, stats = detector.is_likely_blocked()

        # Should detect 6 unique domains in last 5 blocking attempts, but limit display list to 5
        # Note: unique_domains counts domains in the last threshold (5) blocking failures
        # So with 6 domains, the last 5 failures will have at most 5 domains
        assert stats['unique_domains'] >= 2  # At least multi-domain
        assert len(stats['affected_domains']) <= 5  # Display limited to 5


class TestBlockDetectionIntegration:
    """Integration tests for block detection workflow"""

    def test_threshold_edge_case(self):
        """Test exact threshold boundary"""
        detector = BlockDetector(threshold=5, window_size=20)

        # Add exactly 5 failures across 2 domains with high rate
        detector.record_attempt("https://example1.com", success=False, status_code=403)
        detector.record_attempt("https://example2.com", success=False, status_code=403)
        detector.record_attempt("https://example1.com", success=False, status_code=403)
        detector.record_attempt("https://example2.com", success=False, status_code=403)
        detector.record_attempt("https://example1.com", success=False, status_code=403)

        # Total 5, blocking rate = 100%
        is_blocked, stats = detector.is_likely_blocked()
        assert is_blocked is True

    def test_mixed_blocking_types(self):
        """Test different blocking signal types trigger detection"""
        detector = BlockDetector(threshold=5, window_size=20)

        # Mix of 403, 429, and connection errors
        detector.record_attempt("https://example1.com", success=False, status_code=403)
        detector.record_attempt("https://example2.com", success=False, status_code=429)
        detector.record_attempt("https://example3.com", success=False,
                              exception=Exception("Connection reset"))
        detector.record_attempt("https://example1.com", success=False,
                              exception=Exception("TLS error"))
        detector.record_attempt("https://example2.com", success=False, status_code=403)

        is_blocked, stats = detector.is_likely_blocked()
        assert is_blocked is True
        assert stats['blocking_failures'] == 5

    def test_non_blocking_failures_ignored(self):
        """Test 404/500/timeout failures don't count toward blocking"""
        detector = BlockDetector(threshold=5, window_size=20)

        # Add non-blocking failures
        detector.record_attempt("https://example1.com", success=False, status_code=404)
        detector.record_attempt("https://example2.com", success=False, status_code=500)
        detector.record_attempt("https://example3.com", success=False,
                              exception=Exception("Timeout"))

        # Add 5 blocking failures
        for i in range(5):
            detector.record_attempt(f"https://block{i % 2}.com", success=False, status_code=403)

        is_blocked, stats = detector.is_likely_blocked()

        # Should only count blocking failures (5)
        assert stats['blocking_failures'] == 5
        assert stats['total_attempts'] == 8  # 3 non-blocking + 5 blocking
