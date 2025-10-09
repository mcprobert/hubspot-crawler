#!/usr/bin/env python3
"""
HubSpot Crawler v1.7.0 - Advanced Monitor
Detects stalls, tracks progress, and alerts on issues
"""

import time
import os
import sys
from datetime import datetime, timedelta
from typing import Optional, Tuple

class CrawlerMonitor:
    def __init__(self, checkpoint_file: str = "checkpoint.txt",
                 failures_file: str = "failures.jsonl",
                 total_urls: int = 920674,
                 stall_threshold_minutes: int = 10):
        self.checkpoint_file = checkpoint_file
        self.failures_file = failures_file
        self.total_urls = total_urls
        self.stall_threshold = stall_threshold_minutes * 60  # Convert to seconds

        self.last_checkpoint_size = None
        self.last_checkpoint_time = None
        self.last_failures_size = None

    def get_file_stats(self, filepath: str) -> Tuple[int, Optional[float]]:
        """Get line count and last modified time."""
        if not os.path.exists(filepath):
            return 0, None

        # Get line count
        with open(filepath, 'r') as f:
            lines = sum(1 for _ in f)

        # Get last modified time
        mtime = os.path.getmtime(filepath)

        return lines, mtime

    def format_time(self, seconds: float) -> str:
        """Format seconds into human-readable time."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds/60)}m {int(seconds%60)}s"
        else:
            hours = int(seconds / 3600)
            mins = int((seconds % 3600) / 60)
            return f"{hours}h {mins}m"

    def check_stall(self) -> Optional[dict]:
        """Check if crawler has stalled."""
        checkpoint_size, checkpoint_mtime = self.get_file_stats(self.checkpoint_file)
        failures_size, failures_mtime = self.get_file_stats(self.failures_file)

        now = time.time()

        # First run - initialize
        if self.last_checkpoint_time is None:
            self.last_checkpoint_size = checkpoint_size
            self.last_checkpoint_time = checkpoint_mtime or now
            self.last_failures_size = failures_size
            return None

        # Check if any progress made
        progress_made = (checkpoint_size > self.last_checkpoint_size or
                        failures_size > self.last_failures_size)

        if progress_made:
            # Update last known good state
            self.last_checkpoint_size = checkpoint_size
            self.last_checkpoint_time = checkpoint_mtime or now
            self.last_failures_size = failures_size
            return None

        # No progress - check if stalled
        if checkpoint_mtime:
            time_since_update = now - checkpoint_mtime
            if time_since_update > self.stall_threshold:
                return {
                    'stalled': True,
                    'stall_duration': time_since_update,
                    'last_update': datetime.fromtimestamp(checkpoint_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    'checkpoint_size': checkpoint_size,
                    'failures_size': failures_size
                }

        return None

    def get_progress_report(self) -> dict:
        """Get comprehensive progress report."""
        checkpoint_size, checkpoint_mtime = self.get_file_stats(self.checkpoint_file)
        failures_size, failures_mtime = self.get_file_stats(self.failures_file)

        total_processed = checkpoint_size + failures_size
        remaining = self.total_urls - checkpoint_size  # Don't subtract failures (may retry)

        # Calculate progress percentage
        progress_pct = (checkpoint_size / self.total_urls * 100) if self.total_urls > 0 else 0

        # Calculate rate (if we have history)
        rate = None
        eta = None
        if self.last_checkpoint_size is not None and checkpoint_mtime:
            urls_processed = checkpoint_size - self.last_checkpoint_size
            time_elapsed = checkpoint_mtime - self.last_checkpoint_time if self.last_checkpoint_time else 0

            if time_elapsed > 0:
                rate = urls_processed / time_elapsed  # URLs per second
                if rate > 0:
                    eta = remaining / rate  # Seconds remaining

        return {
            'completed': checkpoint_size,
            'failed': failures_size,
            'total_processed': total_processed,
            'remaining': remaining,
            'progress_pct': progress_pct,
            'rate': rate,
            'eta': eta,
            'last_update': datetime.fromtimestamp(checkpoint_mtime).strftime('%Y-%m-%d %H:%M:%S') if checkpoint_mtime else 'Never'
        }

    def print_status(self):
        """Print current status."""
        report = self.get_progress_report()
        stall = self.check_stall()

        os.system('clear' if os.name == 'posix' else 'cls')

        print("=" * 70)
        print("HubSpot Crawler v1.7.0 - Real-Time Monitor")
        print("=" * 70)
        print()

        # Progress
        print(f"Progress:        {report['completed']:,} / {self.total_urls:,} URLs ({report['progress_pct']:.1f}%)")
        print(f"Completed:       {report['completed']:,} URLs")
        print(f"Failed:          {report['failed']:,} URLs")
        print(f"Remaining:       {report['remaining']:,} URLs")
        print()

        # Performance
        if report['rate']:
            urls_per_hour = report['rate'] * 3600
            print(f"Current rate:    {report['rate']:.2f} URLs/sec ({urls_per_hour:.0f} URLs/hour)")
        else:
            print(f"Current rate:    Calculating...")

        if report['eta']:
            print(f"ETA:             {self.format_time(report['eta'])} ({datetime.now() + timedelta(seconds=report['eta']):%Y-%m-%d %H:%M})")
        else:
            print(f"ETA:             Calculating...")

        print()
        print(f"Last update:     {report['last_update']}")

        # Stall detection
        if stall:
            print()
            print("⚠️  " + "=" * 65)
            print("⚠️  STALL DETECTED!")
            print("⚠️  " + "=" * 65)
            print(f"⚠️  No progress for {self.format_time(stall['stall_duration'])}")
            print(f"⚠️  Last update: {stall['last_update']}")
            print(f"⚠️  Checkpoint: {stall['checkpoint_size']:,} URLs")
            print(f"⚠️  Failures: {stall['failures_size']:,} URLs")
            print()
            print("⚠️  Possible causes:")
            print("⚠️    - Process crashed/killed")
            print("⚠️    - Deadlock (should be fixed in v1.7.0)")
            print("⚠️    - Network issues")
            print("⚠️    - Disk full")
            print()
            print("⚠️  Actions:")
            print("⚠️    1. Check process: ps aux | grep hubspot_crawler")
            print("⚠️    2. Check disk space: df -h")
            print("⚠️    3. Check logs for errors")
            print("⚠️    4. Kill and restart if needed")
            print("⚠️  " + "=" * 65)
        else:
            print()
            print("✅ Crawler is running normally")

        print()
        print("=" * 70)
        print(f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Press Ctrl+C to exit")
        print("=" * 70)

def main():
    """Main monitoring loop."""
    import argparse

    parser = argparse.ArgumentParser(description="Monitor HubSpot crawler progress")
    parser.add_argument("--checkpoint", default="checkpoint.txt", help="Checkpoint file path")
    parser.add_argument("--failures", default="failures.jsonl", help="Failures file path")
    parser.add_argument("--total", type=int, default=920674, help="Total URLs to process")
    parser.add_argument("--stall-threshold", type=int, default=10, help="Stall detection threshold in minutes")
    parser.add_argument("--interval", type=int, default=30, help="Update interval in seconds")

    args = parser.parse_args()

    monitor = CrawlerMonitor(
        checkpoint_file=args.checkpoint,
        failures_file=args.failures,
        total_urls=args.total,
        stall_threshold_minutes=args.stall_threshold
    )

    print("Starting crawler monitor...")
    print(f"Stall threshold: {args.stall_threshold} minutes")
    print(f"Update interval: {args.interval} seconds")
    print()

    try:
        while True:
            monitor.print_status()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n\nMonitor stopped.")
        sys.exit(0)

if __name__ == "__main__":
    main()
