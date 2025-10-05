"""
Tests for ProgressTracker class and progress reporting functionality
"""
import time
from hubspot_crawler.crawler import ProgressTracker


class TestProgressTrackerInit:
    """Test ProgressTracker initialization"""

    def test_init_sets_total_urls(self):
        tracker = ProgressTracker(total_urls=100)
        assert tracker.total_urls == 100

    def test_init_sets_start_time(self):
        before = time.time()
        tracker = ProgressTracker(total_urls=10)
        after = time.time()
        assert before <= tracker.start_time <= after

    def test_init_zeros_all_counts(self):
        tracker = ProgressTracker(total_urls=50)
        assert tracker.completed == 0
        assert tracker.success_count == 0
        assert tracker.failure_count == 0
        assert tracker.hubspot_found == 0
        assert tracker.tracking_count == 0
        assert tracker.cms_count == 0
        assert tracker.forms_count == 0
        assert tracker.chat_count == 0
        assert tracker.video_count == 0
        assert tracker.meetings_count == 0
        assert tracker.email_count == 0

    def test_init_zeros_confidence_counts(self):
        tracker = ProgressTracker(total_urls=50)
        assert tracker.definitive_count == 0
        assert tracker.strong_count == 0
        assert tracker.moderate_count == 0
        assert tracker.weak_count == 0

    def test_init_empty_hub_ids(self):
        tracker = ProgressTracker(total_urls=50)
        assert tracker.hub_ids == set()
        assert len(tracker.hub_ids) == 0


class TestProgressTrackerUpdateFromResult:
    """Test update_from_result method"""

    def test_update_tracks_hubspot_found(self):
        tracker = ProgressTracker(total_urls=10)
        result = {
            "summary": {
                "tracking": True,
                "cmsHosting": False,
                "features": {},
                "confidence": "strong"
            },
            "hubIds": []
        }
        tracker.update_from_result(result)
        assert tracker.hubspot_found == 1

    def test_update_ignores_non_hubspot_sites(self):
        tracker = ProgressTracker(total_urls=10)
        result = {
            "summary": {
                "tracking": False,
                "cmsHosting": False,
                "features": {},
                "confidence": "weak"
            },
            "hubIds": []
        }
        tracker.update_from_result(result)
        assert tracker.hubspot_found == 0

    def test_update_tracks_tracking(self):
        tracker = ProgressTracker(total_urls=10)
        result = {
            "summary": {
                "tracking": True,
                "cmsHosting": False,
                "features": {},
                "confidence": "strong"
            },
            "hubIds": []
        }
        tracker.update_from_result(result)
        assert tracker.tracking_count == 1

    def test_update_tracks_cms(self):
        tracker = ProgressTracker(total_urls=10)
        result = {
            "summary": {
                "tracking": False,
                "cmsHosting": True,
                "features": {},
                "confidence": "strong"
            },
            "hubIds": []
        }
        tracker.update_from_result(result)
        assert tracker.cms_count == 1

    def test_update_tracks_all_features(self):
        tracker = ProgressTracker(total_urls=10)
        result = {
            "summary": {
                "tracking": False,
                "cmsHosting": False,
                "features": {
                    "forms": True,
                    "chat": True,
                    "video": True,
                    "meetings": True,
                    "emailTrackingIndicators": True
                },
                "confidence": "strong"
            },
            "hubIds": []
        }
        tracker.update_from_result(result)
        assert tracker.forms_count == 1
        assert tracker.chat_count == 1
        assert tracker.video_count == 1
        assert tracker.meetings_count == 1
        assert tracker.email_count == 1

    def test_update_tracks_confidence_definitive(self):
        tracker = ProgressTracker(total_urls=10)
        result = {
            "summary": {"tracking": True, "cmsHosting": False, "features": {}, "confidence": "definitive"},
            "hubIds": []
        }
        tracker.update_from_result(result)
        assert tracker.definitive_count == 1

    def test_update_tracks_confidence_strong(self):
        tracker = ProgressTracker(total_urls=10)
        result = {
            "summary": {"tracking": True, "cmsHosting": False, "features": {}, "confidence": "strong"},
            "hubIds": []
        }
        tracker.update_from_result(result)
        assert tracker.strong_count == 1

    def test_update_tracks_confidence_moderate(self):
        tracker = ProgressTracker(total_urls=10)
        result = {
            "summary": {"tracking": True, "cmsHosting": False, "features": {}, "confidence": "moderate"},
            "hubIds": []
        }
        tracker.update_from_result(result)
        assert tracker.moderate_count == 1

    def test_update_tracks_confidence_weak(self):
        tracker = ProgressTracker(total_urls=10)
        result = {
            "summary": {"tracking": False, "cmsHosting": False, "features": {}, "confidence": "weak"},
            "hubIds": []
        }
        tracker.update_from_result(result)
        assert tracker.weak_count == 1

    def test_update_tracks_hub_ids(self):
        tracker = ProgressTracker(total_urls=10)
        result = {
            "summary": {"tracking": True, "cmsHosting": False, "features": {}, "confidence": "strong"},
            "hubIds": [12345, 67890]
        }
        tracker.update_from_result(result)
        assert 12345 in tracker.hub_ids
        assert 67890 in tracker.hub_ids
        assert len(tracker.hub_ids) == 2

    def test_update_deduplicates_hub_ids(self):
        tracker = ProgressTracker(total_urls=10)
        result1 = {
            "summary": {"tracking": True, "cmsHosting": False, "features": {}, "confidence": "strong"},
            "hubIds": [12345]
        }
        result2 = {
            "summary": {"tracking": True, "cmsHosting": False, "features": {}, "confidence": "strong"},
            "hubIds": [12345, 67890]
        }
        tracker.update_from_result(result1)
        tracker.update_from_result(result2)
        assert len(tracker.hub_ids) == 2
        assert 12345 in tracker.hub_ids
        assert 67890 in tracker.hub_ids

    def test_update_ignores_non_integer_hub_ids(self):
        tracker = ProgressTracker(total_urls=10)
        result = {
            "summary": {"tracking": True, "cmsHosting": False, "features": {}, "confidence": "strong"},
            "hubIds": [12345, "invalid", None, 67890]
        }
        tracker.update_from_result(result)
        assert len(tracker.hub_ids) == 2
        assert 12345 in tracker.hub_ids
        assert 67890 in tracker.hub_ids


class TestProgressTrackerMetrics:
    """Test metric calculation methods"""

    def test_get_elapsed_time(self):
        tracker = ProgressTracker(total_urls=10)
        time.sleep(0.1)
        elapsed = tracker.get_elapsed_time()
        assert elapsed >= 0.1
        assert elapsed < 1.0  # Should be quick

    def test_get_rate_with_no_time(self):
        tracker = ProgressTracker(total_urls=10)
        tracker.start_time = time.time()  # Reset to now
        rate = tracker.get_rate()
        # Rate might be very high or 0 depending on timing
        assert rate >= 0.0

    def test_get_rate_with_progress(self):
        tracker = ProgressTracker(total_urls=100)
        tracker.start_time = time.time() - 10  # 10 seconds ago
        tracker.completed = 50
        rate = tracker.get_rate()
        assert rate >= 4.0  # At least 4 URLs/sec (50 in 10 seconds)
        assert rate <= 6.0  # No more than 6 URLs/sec

    def test_get_percentage_zero(self):
        tracker = ProgressTracker(total_urls=100)
        assert tracker.get_percentage() == 0.0

    def test_get_percentage_half(self):
        tracker = ProgressTracker(total_urls=100)
        tracker.completed = 50
        assert tracker.get_percentage() == 50.0

    def test_get_percentage_complete(self):
        tracker = ProgressTracker(total_urls=100)
        tracker.completed = 100
        assert tracker.get_percentage() == 100.0

    def test_get_eta_with_no_progress(self):
        tracker = ProgressTracker(total_urls=100)
        eta = tracker.get_eta()
        assert eta == 0.0

    def test_get_eta_with_progress(self):
        tracker = ProgressTracker(total_urls=100)
        tracker.start_time = time.time() - 10  # 10 seconds ago
        tracker.completed = 50
        eta = tracker.get_eta()
        # Should be roughly 10 seconds remaining (50 remaining at 5 URL/sec)
        assert eta >= 8.0
        assert eta <= 12.0

    def test_format_time_seconds(self):
        tracker = ProgressTracker(total_urls=10)
        assert tracker.format_time(45) == "0:45"

    def test_format_time_minutes(self):
        tracker = ProgressTracker(total_urls=10)
        assert tracker.format_time(125) == "2:05"

    def test_format_time_hours(self):
        tracker = ProgressTracker(total_urls=10)
        assert tracker.format_time(3665) == "1:01:05"


class TestProgressTrackerOutputFormats:
    """Test output formatting methods"""

    def test_get_compact_status_no_results(self):
        tracker = ProgressTracker(total_urls=100)
        tracker.completed = 10
        tracker.success_count = 0
        tracker.failure_count = 10
        status = tracker.get_compact_status()
        assert "10/100" in status
        assert "10.0%" in status
        assert "Success: 0" in status
        assert "Failed: 10" in status
        assert "Rate:" in status
        assert "Elapsed:" in status
        assert "ETA:" in status
        # Should not show HubSpot stats with no successful results
        assert "HubSpot Found" not in status

    def test_get_compact_status_with_results(self):
        tracker = ProgressTracker(total_urls=100)
        tracker.completed = 20
        tracker.success_count = 18
        tracker.failure_count = 2
        tracker.hubspot_found = 10
        tracker.hub_ids = {123, 456, 789}
        status = tracker.get_compact_status()
        assert "20/100" in status
        assert "20.0%" in status
        assert "HubSpot Found: 10/18" in status
        assert "Hub IDs: 3 unique" in status

    def test_get_detailed_status_with_results(self):
        tracker = ProgressTracker(total_urls=100)
        tracker.completed = 50
        tracker.success_count = 45
        tracker.failure_count = 5
        tracker.hubspot_found = 30
        tracker.tracking_count = 28
        tracker.cms_count = 15
        tracker.forms_count = 10
        tracker.chat_count = 5
        tracker.definitive_count = 20
        tracker.strong_count = 10
        tracker.moderate_count = 5
        tracker.weak_count = 0
        tracker.hub_ids = {123, 456}

        status = tracker.get_detailed_status()
        assert "50/100" in status
        assert "50.0%" in status
        assert "HubSpot Found: 30/45" in status
        assert "Tracking: 28" in status
        assert "CMS: 15" in status
        assert "Forms: 10" in status
        assert "Chat: 5" in status
        assert "Definitive: 20" in status
        assert "Strong: 10" in status
        assert "Moderate: 5" in status
        assert "Hub IDs: 2 unique" in status

    def test_get_json_status(self):
        import json
        tracker = ProgressTracker(total_urls=100)
        tracker.completed = 25
        tracker.success_count = 20
        tracker.failure_count = 5
        tracker.hubspot_found = 12
        tracker.tracking_count = 10
        tracker.hub_ids = {123, 456, 789}

        json_str = tracker.get_json_status()
        data = json.loads(json_str)

        assert data["progress"]["completed"] == 25
        assert data["progress"]["total"] == 100
        assert data["progress"]["percentage"] == 25.0
        assert data["progress"]["success"] == 20
        assert data["progress"]["failed"] == 5
        assert data["hubspot_detection"]["found"] == 12
        assert data["hubspot_detection"]["tracking"] == 10
        assert data["hubspot_detection"]["unique_hub_ids"] == 3
        assert "performance" in data
        assert "confidence" in data
