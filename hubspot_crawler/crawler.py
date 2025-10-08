
import asyncio
import re
import sys
import json
import time
import random
import urllib.parse
import select
from collections import deque
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any, Set

import httpx
from bs4 import BeautifulSoup
from .detector import detect_html, detect_network, make_result, RX

# Optional: jsonschema validation
try:
    import jsonschema
    _HAS_JSONSCHEMA = True
except Exception:
    _HAS_JSONSCHEMA = False

# Optional: playwright for dynamic render
try:
    from playwright.async_api import async_playwright
    _HAS_PLAYWRIGHT = True
except Exception:
    _HAS_PLAYWRIGHT = False


DEFAULT_UA = "WhitehatHubSpotCrawler/1.0 (+https://whitehat-seo.co.uk)"
TIMEOUT = 20.0


def extract_page_metadata(html: str) -> dict:
    """
    Extract basic page metadata from HTML.

    Returns dict with:
        - title: Content of <title> tag (or None)
        - description: Content of meta description tag (or None)
    """
    try:
        soup = BeautifulSoup(html, "lxml")

        # Extract title
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""
        title = title if title else None  # Convert empty string to None

        # Extract meta description
        description = None
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            description = meta_desc.get("content", "").strip() or None

        return {
            "title": title,
            "description": description
        }
    except Exception:
        # If parsing fails, return None values
        return {
            "title": None,
            "description": None
        }


class ProgressTracker:
    """Tracks detailed statistics for progress reporting during crawls"""

    def __init__(self, total_urls: int):
        self.total_urls = total_urls
        self.start_time = time.time()

        # URL processing counts
        self.completed = 0
        self.success_count = 0
        self.failure_count = 0

        # HubSpot detection statistics
        self.hubspot_found = 0  # Sites with any HubSpot presence
        self.tracking_count = 0
        self.cms_count = 0
        self.forms_count = 0
        self.chat_count = 0
        self.video_count = 0
        self.meetings_count = 0
        self.email_count = 0

        # Confidence distribution
        self.definitive_count = 0
        self.strong_count = 0
        self.moderate_count = 0
        self.weak_count = 0

        # Hub IDs
        self.hub_ids: Set[int] = set()

    def update_from_result(self, result: dict):
        """Update statistics from a successful detection result"""
        # Check if HubSpot was found (any positive indicator)
        summary = result.get("summary", {})
        has_hubspot = (
            summary.get("tracking", False) or
            summary.get("cmsHosting", False) or
            any(summary.get("features", {}).values())
        )

        if has_hubspot:
            self.hubspot_found += 1

        # Track individual features
        if summary.get("tracking"):
            self.tracking_count += 1
        if summary.get("cmsHosting"):
            self.cms_count += 1

        features = summary.get("features", {})
        if features.get("forms"):
            self.forms_count += 1
        if features.get("chat"):
            self.chat_count += 1
        if features.get("video"):
            self.video_count += 1
        if features.get("meetings"):
            self.meetings_count += 1
        if features.get("emailTrackingIndicators"):
            self.email_count += 1

        # Track confidence
        confidence = summary.get("confidence", "").lower()
        if confidence == "definitive":
            self.definitive_count += 1
        elif confidence == "strong":
            self.strong_count += 1
        elif confidence == "moderate":
            self.moderate_count += 1
        elif confidence == "weak":
            self.weak_count += 1

        # Track Hub IDs
        for hub_id in result.get("hubIds", []):
            if isinstance(hub_id, int):
                self.hub_ids.add(hub_id)

    def get_elapsed_time(self) -> float:
        """Get elapsed time in seconds"""
        return time.time() - self.start_time

    def get_rate(self) -> float:
        """Get URLs per second"""
        elapsed = self.get_elapsed_time()
        return self.completed / elapsed if elapsed > 0 else 0.0

    def get_eta(self) -> float:
        """Get estimated time remaining in seconds"""
        rate = self.get_rate()
        if rate > 0:
            remaining = self.total_urls - self.completed
            return remaining / rate
        return 0.0

    def get_percentage(self) -> float:
        """Get percentage complete"""
        return (self.completed / self.total_urls * 100) if self.total_urls > 0 else 0.0

    def format_time(self, seconds: float) -> str:
        """Format seconds as H:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"

    def get_compact_status(self) -> str:
        """Get compact single-line status"""
        pct = self.get_percentage()
        rate = self.get_rate()
        elapsed = self.get_elapsed_time()
        eta = self.get_eta()

        line1 = f"Progress: {self.completed}/{self.total_urls} ({pct:.1f}%) | Success: {self.success_count} | Failed: {self.failure_count} | Rate: {rate:.1f} URL/s | Elapsed: {self.format_time(elapsed)} | ETA: {self.format_time(eta)}"

        # HubSpot statistics (only if we have successful results)
        if self.success_count > 0:
            hs_pct = (self.hubspot_found / self.success_count * 100) if self.success_count > 0 else 0.0
            line2 = f"HubSpot Found: {self.hubspot_found}/{self.success_count} ({hs_pct:.1f}%) | Hub IDs: {len(self.hub_ids)} unique"
            return f"{line1}\n{line2}"

        return line1

    def get_detailed_status(self) -> str:
        """Get detailed multi-line status"""
        pct = self.get_percentage()
        rate = self.get_rate()
        elapsed = self.get_elapsed_time()
        eta = self.get_eta()

        lines = [
            f"Progress: {self.completed}/{self.total_urls} ({pct:.1f}%) | Success: {self.success_count} | Failed: {self.failure_count} | Rate: {rate:.1f} URL/s | Elapsed: {self.format_time(elapsed)} | ETA: {self.format_time(eta)}"
        ]

        # HubSpot statistics (only if we have successful results)
        if self.success_count > 0:
            hs_pct = (self.hubspot_found / self.success_count * 100) if self.success_count > 0 else 0.0
            lines.append(f"HubSpot Found: {self.hubspot_found}/{self.success_count} ({hs_pct:.1f}%) | Tracking: {self.tracking_count} | CMS: {self.cms_count} | Forms: {self.forms_count} | Chat: {self.chat_count}")
            lines.append(f"Confidence: Definitive: {self.definitive_count} | Strong: {self.strong_count} | Moderate: {self.moderate_count} | Weak: {self.weak_count} | Hub IDs: {len(self.hub_ids)} unique")

        return "\n".join(lines)

    def get_json_status(self) -> str:
        """Get status as JSON string"""
        data = {
            "progress": {
                "completed": self.completed,
                "total": self.total_urls,
                "percentage": round(self.get_percentage(), 2),
                "success": self.success_count,
                "failed": self.failure_count
            },
            "performance": {
                "rate_urls_per_sec": round(self.get_rate(), 2),
                "elapsed_seconds": round(self.get_elapsed_time(), 2),
                "eta_seconds": round(self.get_eta(), 2)
            },
            "hubspot_detection": {
                "found": self.hubspot_found,
                "tracking": self.tracking_count,
                "cms": self.cms_count,
                "forms": self.forms_count,
                "chat": self.chat_count,
                "video": self.video_count,
                "meetings": self.meetings_count,
                "email": self.email_count,
                "unique_hub_ids": len(self.hub_ids)
            },
            "confidence": {
                "definitive": self.definitive_count,
                "strong": self.strong_count,
                "moderate": self.moderate_count,
                "weak": self.weak_count
            }
        }
        return json.dumps(data)


class BlockDetector:
    """Detects potential IP blocking by tracking failure patterns across multiple domains"""

    def __init__(self, threshold: int = 5, window_size: int = 20):
        """
        Initialize block detector.

        Args:
            threshold: Number of blocking failures to trigger alert
            window_size: Size of sliding window for tracking attempts
        """
        self.threshold = threshold
        self.window_size = window_size
        # Track recent attempts: (url, domain, is_blocking, timestamp)
        self.recent_attempts: deque = deque(maxlen=window_size)
        # Track failed URLs for potential retry
        self.failed_urls_for_retry: deque = deque(maxlen=50)

    def record_attempt(self, url: str, success: bool, status_code: Optional[int] = None,
                      exception: Optional[Exception] = None):
        """
        Record an attempt and classify if it's a blocking signal.

        Blocking signals include:
        - HTTP 403 (Forbidden) or 429 (Rate Limit)
        - Connection errors, TLS failures, connection resets
        """
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc

        # Determine if this is a blocking-type failure
        is_blocking = False
        if not success:
            # HTTP status codes that indicate blocking
            if status_code in [403, 429]:
                is_blocking = True
            # Network-level errors that indicate blocking
            elif exception:
                error_msg = str(exception).lower()
                blocking_errors = [
                    'connection reset',
                    'tls',
                    'ssl',
                    'clientconnectorerror',
                    'connectionreseterror'
                ]
                is_blocking = any(err in error_msg for err in blocking_errors)

        self.recent_attempts.append((url, domain, is_blocking, time.time()))

        # Save failed URLs for potential retry
        if not success and is_blocking:
            self.failed_urls_for_retry.append(url)

    def is_likely_blocked(self) -> Tuple[bool, dict]:
        """
        Check if failure pattern indicates IP blocking.

        Returns:
            Tuple of (is_blocked, stats_dict)

        Logic:
        - Must meet threshold of blocking failures
        - Must affect multiple domains (not just one problematic site)
        - Must have high blocking rate (≥60% of recent attempts)
        """
        # Extract blocking failures from recent attempts
        blocking_failures = [
            (url, domain)
            for url, domain, is_blocking, _ in self.recent_attempts
            if is_blocking
        ]

        # Not enough blocking failures to trigger
        if len(blocking_failures) < self.threshold:
            return False, {}

        # Check if recent blocking failures span multiple domains
        recent_blocking = blocking_failures[-self.threshold:]
        unique_domains = set(domain for _, domain in recent_blocking)

        # Calculate blocking rate within the window
        total_in_window = len(self.recent_attempts)
        blocking_rate = len(blocking_failures) / max(total_in_window, 1)

        # Trigger blocking alert if:
        # 1. Threshold of blocking failures met
        # 2. Multiple domains affected (≥2) - single domain issues don't indicate IP block
        # 3. High blocking rate (≥60%) - prevents false positives in large crawls
        is_blocked = (
            len(blocking_failures) >= self.threshold and
            len(unique_domains) >= 2 and
            blocking_rate >= 0.6
        )

        # Gather statistics for reporting
        stats = {
            'blocking_failures': len(blocking_failures),
            'total_attempts': total_in_window,
            'blocking_rate': blocking_rate,
            'unique_domains': len(unique_domains),
            'affected_domains': list(unique_domains)[:5],  # Show first 5 domains
            'retry_queue_size': len(self.failed_urls_for_retry)
        }

        return is_blocked, stats

    def get_retry_urls(self) -> List[str]:
        """Get list of failed URLs available for retry"""
        return list(self.failed_urls_for_retry)

    def reset(self):
        """Reset the detector state (called after handling a block)"""
        self.recent_attempts.clear()
        # Keep retry queue for user to access


def normalize_url(url: str) -> str:
    u = urllib.parse.urlsplit(url)
    if not u.scheme:
        url = "https://" + url
    return url

def generate_url_variations(url: str, max_variations: int = 4) -> List[str]:
    """Generate common URL variations to try on failure.

    Tries common fixes for malformed URLs in priority order:
    1. Add/remove www prefix
    2. Switch http/https scheme
    3. Add trailing slash
    4. Remove trailing slash

    Args:
        url: The original URL that failed
        max_variations: Maximum number of variations to generate (default: 4)

    Returns:
        List of URL variations in priority order (most likely to work first)
    """
    variations = []
    parsed = urllib.parse.urlparse(url)

    # Variation 1: Add/remove www prefix
    if parsed.netloc.startswith('www.'):
        # Try without www
        new_netloc = parsed.netloc[4:]
        variations.append(urllib.parse.urlunparse(parsed._replace(netloc=new_netloc)))
    else:
        # Try with www
        new_netloc = 'www.' + parsed.netloc
        variations.append(urllib.parse.urlunparse(parsed._replace(netloc=new_netloc)))

    # Variation 2: Switch scheme (https ↔ http)
    opposite_scheme = 'http' if parsed.scheme == 'https' else 'https'
    variations.append(urllib.parse.urlunparse(parsed._replace(scheme=opposite_scheme)))

    # Variation 3: Add trailing slash (if not present)
    if not parsed.path.endswith('/'):
        variations.append(urllib.parse.urlunparse(parsed._replace(path=parsed.path + '/')))

    # Variation 4: Remove trailing slash (if present and not root)
    if parsed.path.endswith('/') and parsed.path != '/':
        variations.append(urllib.parse.urlunparse(parsed._replace(path=parsed.path.rstrip('/'))))

    # Remove duplicates while preserving order
    seen = set()
    unique_variations = []
    for v in variations:
        if v not in seen and v != url:  # Don't include original URL
            seen.add(v)
            unique_variations.append(v)

    return unique_variations[:max_variations]

def extract_resource_urls(html: str, base_url: str) -> List[str]:
    """Extract resource URLs from HTML - scripts, stylesheets, iframes only.
    Excludes <a> tags to avoid navigation link noise."""
    soup = BeautifulSoup(html, "lxml")
    urls: Set[str] = set()
    # Only extract actual resources, not navigation links
    for tag, attr in (("script","src"),("link","href"),("iframe","src")):
        for el in soup.find_all(tag):
            href = el.get(attr)
            if not href: continue
            try:
                absu = urllib.parse.urljoin(base_url, href)
                urls.add(absu)
            except Exception:
                continue
    return list(urls)


async def handle_pause_prompt(pause_event: asyncio.Event, block_detector: BlockDetector,
                              auto_resume_secs: int, quiet: bool = False):
    """
    Handle user prompt during blocking pause with timeout for headless environments.

    Args:
        pause_event: Event to set when resuming
        block_detector: BlockDetector instance to get retry URLs from
        auto_resume_secs: Seconds to wait before auto-resuming (0 = wait indefinitely)
        quiet: If True, auto-resume immediately (can't show interactive prompt)
    """
    # In quiet mode or headless environment, auto-resume immediately
    if quiet or not sys.stdin.isatty():
        print("⚠️  Block detected but running in quiet/headless mode - auto-resuming", file=sys.stderr)
        print(f"▶️  Resuming all workers (pause_event.set())", file=sys.stderr)
        pause_event.set()
        return

    def prompt_with_timeout():
        """Blocking input with timeout (runs in thread pool)"""
        print("\n" + "="*60, file=sys.stderr)
        print("🛑 CRAWL PAUSED - Blocking detected", file=sys.stderr)
        print("="*60, file=sys.stderr)
        print("\nOptions:", file=sys.stderr)
        print("  [c] Continue crawling from current position", file=sys.stderr)
        print("  [q] Quit gracefully (checkpoint saved)", file=sys.stderr)

        if auto_resume_secs > 0:
            print(f"\n⏰ Auto-resume in {auto_resume_secs}s if no input...\n", file=sys.stderr)

        print("Your choice [c/q]: ", file=sys.stderr, end='', flush=True)

        try:
            if auto_resume_secs > 0:
                # Check if stdin has data with timeout
                ready, _, _ = select.select([sys.stdin], [], [], auto_resume_secs)
                if ready:
                    choice = sys.stdin.readline().strip().lower()
                else:
                    print("\n⏰ Auto-resuming (timeout)", file=sys.stderr)
                    return 'c'
            else:
                # Wait indefinitely for input
                choice = input().strip().lower()

            return choice if choice in ['c', 'q'] else 'c'

        except Exception as e:
            # If input fails (e.g., no TTY), auto-resume
            print(f"\n⚠️  Input error ({e}), auto-resuming", file=sys.stderr)
            return 'c'

    # Run blocking input in thread pool to avoid blocking event loop
    loop = asyncio.get_event_loop()
    choice = await loop.run_in_executor(None, prompt_with_timeout)

    if choice == 'q':
        print("\n✅ Quitting gracefully (checkpoint saved)...", file=sys.stderr)
        sys.exit(0)

    # Resume crawling
    print(f"\n▶️  Resuming crawl (pause_event.set())...\n", file=sys.stderr)
    pause_event.set()


async def block_detection_coordinator(detector_queue: asyncio.Queue, pause_event: asyncio.Event,
                                      block_detector: BlockDetector, block_action: str,
                                      auto_resume_secs: int, quiet: bool = False):
    """
    Monitor attempts for blocking patterns and handle pause/resume.

    Args:
        detector_queue: Queue receiving attempt reports from workers
        pause_event: Event to control worker pause/resume
        block_detector: BlockDetector instance
        block_action: Action to take on block detection (pause/warn/abort)
        auto_resume_secs: Seconds before auto-resume in headless mode
        quiet: If True, suppress interactive prompts
    """
    try:
        while True:
            attempt = await detector_queue.get()

            # Poison pill signals shutdown
            if attempt is None:
                detector_queue.task_done()
                break

            # Record attempt in block detector
            block_detector.record_attempt(
                attempt['url'],
                attempt['success'],
                attempt.get('status_code'),
                attempt.get('exception')
            )

            # Check for blocking pattern
            is_blocked, stats = block_detector.is_likely_blocked()

            if is_blocked:
                # Pause all workers
                print(f"🛑 Pausing all workers (pause_event.clear())", file=sys.stderr)
                pause_event.clear()

                # Print detailed alert
                print("\n" + "="*70, file=sys.stderr)
                print("⚠️  IP BLOCKING DETECTED", file=sys.stderr)
                print("="*70, file=sys.stderr)
                print(f"📊 Statistics:", file=sys.stderr)
                print(f"   • {stats['blocking_failures']}/{stats['total_attempts']} recent attempts blocked ({stats['blocking_rate']:.0%})", file=sys.stderr)
                print(f"   • {stats['unique_domains']} different domains affected", file=sys.stderr)
                print(f"   • Affected domains: {', '.join(stats['affected_domains'])}", file=sys.stderr)
                print(f"   • {stats['retry_queue_size']} URLs queued for potential retry", file=sys.stderr)
                print("="*70, file=sys.stderr)

                # Take configured action
                if block_action == 'pause':
                    await handle_pause_prompt(pause_event, block_detector, auto_resume_secs, quiet)

                elif block_action == 'warn':
                    print("⚠️  Continuing anyway (--block-action warn)", file=sys.stderr)
                    print(f"▶️  Resuming all workers (pause_event.set())\n", file=sys.stderr)
                    pause_event.set()

                elif block_action == 'abort':
                    print("❌ Aborting crawl (--block-action abort)", file=sys.stderr)
                    sys.exit(1)

                # Reset detector after handling block
                block_detector.reset()

            detector_queue.task_done()
    finally:
        # Ensure workers are always resumed even if coordinator crashes
        if not pause_event.is_set():
            print(f"⚠️  Coordinator cleanup - ensuring workers resumed", file=sys.stderr)
            pause_event.set()


async def fetch_html(client: httpx.AsyncClient, url: str) -> Tuple[str, Dict[str, str], int, str]:
    """Fetch HTML with error handling. Returns (html, headers, status_code, final_url)"""
    try:
        r = await client.get(url, timeout=TIMEOUT, follow_redirects=True)
        r.raise_for_status()  # Raise on 4xx/5xx
        headers = {k: v for k, v in r.headers.items() if k and v}
        final_url = str(r.url)  # Capture final URL after redirects
        return r.text, headers, r.status_code, final_url
    except httpx.HTTPStatusError as e:
        # 4xx/5xx errors - still try to parse body if available
        headers = {k: v for k, v in e.response.headers.items() if k and v}
        status_code = e.response.status_code if e.response else 0
        final_url = str(e.response.url) if e.response else url
        return e.response.text if e.response else "", headers, status_code, final_url
    except (httpx.RequestError, httpx.TimeoutException) as e:
        # Network errors, DNS failures, timeouts
        raise RuntimeError(f"HTTP error fetching {url}: {str(e)}") from e

async def render_with_playwright(url: str, user_agent: str) -> Tuple[str, List[str], Dict[str,str], int, str]:
    if not _HAS_PLAYWRIGHT:
        raise RuntimeError("playwright not installed. pip install playwright && playwright install chromium")
    network: List[str] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=user_agent, ignore_https_errors=True)
        page = await ctx.new_page()
        page.on("request", lambda req: network.append(req.url))
        resp = await page.goto(url, wait_until="load", timeout=30000)
        html = await page.content()
        headers = {}
        status_code = 0
        final_url = url  # Default to original if no response
        if resp:
            headers = {k: v for k, v in resp.headers.items()}
            status_code = resp.status
            final_url = page.url  # Get final URL after redirects
        # wait a bit for late beacons
        await page.wait_for_timeout(1500)
        await ctx.close()
        await browser.close()
    return html, network, headers, status_code, final_url

async def process_url(original_url: str, url: str, client: httpx.AsyncClient, render: bool, validate: bool) -> dict:
    """Process a URL and return detection results. Raises on fatal errors.

    Args:
        original_url: The exact URL from the input file (before normalization)
        url: The normalized URL to actually fetch
        client: httpx client
        render: Whether to use Playwright rendering
        validate: Whether to validate against schema
    """
    html = ""
    headers: Dict[str,str] = {}
    status_code = 0
    final_url = url  # Default to normalized URL
    network_lines: List[str] = []

    try:
        if render and _HAS_PLAYWRIGHT:
            try:
                html, network_lines, headers, status_code, final_url = await render_with_playwright(url, client.headers.get("user-agent", DEFAULT_UA))
            except Exception as e:
                # Fall back to static if render fails
                print(f"Playwright render failed for {url}, falling back to static: {e}", file=sys.stderr)
                html, headers, status_code, final_url = await fetch_html(client, url)
                network_lines = extract_resource_urls(html, url)
        else:
            html, headers, status_code, final_url = await fetch_html(client, url)
            network_lines = extract_resource_urls(html, url)
    except Exception as e:
        # Fatal HTTP/network error - re-raise with context
        raise RuntimeError(f"Failed to fetch {url}: {str(e)}") from e

    # For HTTP error responses (4xx/5xx), set final_url = original_url
    # since we didn't get usable content to analyze
    if status_code >= 400:
        final_url = original_url

    ev = []
    ev.extend(detect_html(html))
    ev.extend(detect_network("\n".join(network_lines)))

    # Deduplicate evidence based on (category, patternId, source, truncated match)
    seen = set()
    deduped_ev = []
    for e in ev:
        key = (e["category"], e["patternId"], e["source"], e["match"][:300])
        if key not in seen:
            seen.add(key)
            deduped_ev.append(e)
    ev = deduped_ev

    # Inspect Set-Cookie headers for cookie names
    # httpx returns headers as a multi-dict, we need to get all Set-Cookie headers
    if hasattr(headers, 'get_list'):
        set_cookie_headers = headers.get_list("Set-Cookie") or headers.get_list("set-cookie") or []
    else:
        # Fallback for regular dict
        set_cookie_val = headers.get("set-cookie") or headers.get("Set-Cookie")
        set_cookie_headers = [set_cookie_val] if set_cookie_val else []

    for cookie_header in set_cookie_headers:
        if not cookie_header:
            continue
        # Check for HubSpot cookie names at the start of each Set-Cookie value
        for m in re.finditer(RX["cookie_any"], cookie_header):
            cookie_name = m.group(0)
            # hubspotutk is definitive tracking evidence
            confidence = "definitive" if cookie_name.lower() == "hubspotutk" else "strong"
            ev.append({
                "category": "cookies",
                "patternId": "cookie_any",
                "match": cookie_name[:300],  # Truncate to 300 chars
                "source": "header",
                "hubId": None,
                "confidence": confidence
            })

    # Extract page metadata
    page_metadata = extract_page_metadata(html)

    result = make_result(original_url, final_url, ev, headers=headers, http_status=status_code, page_metadata=page_metadata)

    if validate and _HAS_JSONSCHEMA:
        import importlib.resources as pkg_resources
        from . import schemas as _schemas_pkg
        schema_text = pkg_resources.files(_schemas_pkg).joinpath("hubspot_detection_result.schema.json").read_text()
        schema = json.loads(schema_text)
        jsonschema.validate(instance=result, schema=schema)

    return result

def flatten_result_for_csv(result: dict) -> dict:
    """
    Flatten a nested detection result dict into a flat dict suitable for CSV export.

    Extracts values from nested summary/features and formats complex types.
    """
    summary = result.get("summary", {})
    features = summary.get("features", {})
    page_metadata = result.get("page_metadata", {})

    # Format hub IDs as comma-separated string
    hub_ids = result.get("hubIds", [])
    hub_ids_str = ",".join(str(hid) for hid in hub_ids) if hub_ids else ""

    return {
        "original_url": result.get("original_url", ""),
        "final_url": result.get("final_url", ""),
        "timestamp": result.get("timestamp", ""),
        "hubspot_detected": result.get("hubspot_detected", False),
        "tracking": summary.get("tracking", False),
        "cms_hosting": summary.get("cmsHosting", False),
        "confidence": summary.get("confidence", ""),
        "forms": features.get("forms", False),
        "chat": features.get("chat", False),
        "ctas_legacy": features.get("ctasLegacy", False),
        "meetings": features.get("meetings", False),
        "video": features.get("video", False),
        "email_tracking": features.get("emailTrackingIndicators", False),
        "hub_ids": hub_ids_str,
        "hub_id_count": len(hub_ids),
        "evidence_count": len(result.get("evidence", [])),
        "http_status": result.get("http_status", ""),
        "page_title": (page_metadata.get("title") or "") if page_metadata else "",
        "page_description": (page_metadata.get("description") or "") if page_metadata else ""
    }

async def csv_writer_worker(queue: asyncio.Queue, output_file: Optional[str]):
    """CSV writer coroutine that writes flattened results to CSV format."""
    import csv

    # CSV field names in order (19 columns total)
    fieldnames = [
        "original_url", "final_url", "timestamp", "hubspot_detected", "tracking", "cms_hosting", "confidence",
        "forms", "chat", "ctas_legacy", "meetings", "video", "email_tracking",
        "hub_ids", "hub_id_count", "evidence_count", "http_status", "page_title", "page_description"
    ]

    if output_file:
        f = open(output_file, "w", encoding="utf-8", newline='')
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
    else:
        f = None
        writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
        writer.writeheader()

    try:
        while True:
            item = await queue.get()

            # Poison pill signals shutdown
            if item is None:
                break

            # Flatten and write (move to thread to avoid blocking event loop)
            flat_row = flatten_result_for_csv(item)
            await asyncio.to_thread(writer.writerow, flat_row)
            if f:
                await asyncio.to_thread(f.flush)

            queue.task_done()
    finally:
        if f:
            f.close()

async def excel_writer_worker(queue: asyncio.Queue, output_file: str):
    """Excel writer coroutine that writes flattened results to .xlsx format."""
    try:
        import openpyxl
        from openpyxl import Workbook
        from openpyxl.styles import Font
    except ImportError:
        raise RuntimeError("openpyxl not installed. Install with: pip install 'hubspot-crawler[excel]' or pip install openpyxl")

    # Create workbook and worksheet
    wb = Workbook()
    ws = wb.active
    ws.title = "HubSpot Detection Results"

    # Field names in order (19 columns total)
    fieldnames = [
        "original_url", "final_url", "timestamp", "hubspot_detected", "tracking", "cms_hosting", "confidence",
        "forms", "chat", "ctas_legacy", "meetings", "video", "email_tracking",
        "hub_ids", "hub_id_count", "evidence_count", "http_status", "page_title", "page_description"
    ]

    # Write headers
    ws.append(fieldnames)

    # Make header row bold
    for cell in ws[1]:
        cell.font = Font(bold=True)

    try:
        while True:
            item = await queue.get()

            # Poison pill signals shutdown
            if item is None:
                break

            # Flatten and convert to row
            flat_row = flatten_result_for_csv(item)
            row_values = [flat_row.get(field, "") for field in fieldnames]
            ws.append(row_values)

            queue.task_done()
    finally:
        # Save workbook (move to thread to avoid blocking event loop)
        await asyncio.to_thread(wb.save, output_file)

async def writer_worker(queue: asyncio.Queue, output_file: Optional[str], pretty: bool = False):
    """Single writer coroutine that drains queue and writes to file or stdout.
    Eliminates file write race condition by centralizing all writes."""

    if output_file:
        f = open(output_file, "w", encoding="utf-8")
    else:
        f = None

    try:
        while True:
            item = await queue.get()

            # Poison pill signals shutdown
            if item is None:
                break

            # Format and write
            line = json.dumps(item, indent=2 if pretty else None)
            if f:
                f.write(line + "\n")
                f.flush()  # Ensure data written
            else:
                print(line)

            queue.task_done()
    finally:
        if f:
            f.close()

async def run(urls: List[str], concurrency: int = 2, render: bool = False, validate: bool = False, user_agent: str = DEFAULT_UA, output: Optional[str] = None, output_format: str = "jsonl", pretty: bool = False, max_retries: int = 3, failures_output: Optional[str] = None, checkpoint_file: Optional[str] = None, try_variations: bool = False, max_variations: int = 4, progress_interval: int = 10, progress_style: str = "compact", quiet: bool = False, delay: float = 3.0, jitter: float = 1.0, max_per_domain: int = 1, block_detection: bool = False, block_threshold: int = 5, block_window: int = 20, block_action: str = "pause", block_auto_resume: int = 300, insecure: bool = False):
    # DEADLOCK FIX: Disable connection pooling to prevent CLOSE_WAIT accumulation
    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=0)

    # Create queue for results (bounded to prevent memory issues)
    result_queue = asyncio.Queue(maxsize=concurrency * 2)

    # Create queue for failures
    failure_queue = asyncio.Queue(maxsize=concurrency * 2) if failures_output else None

    # Start single writer task (choose format based on output_format parameter)
    if output_format == "csv":
        writer_task = asyncio.create_task(csv_writer_worker(result_queue, output))
    elif output_format == "xlsx":
        if not output:
            raise ValueError("Excel format (xlsx) requires --out parameter (cannot write to stdout)")
        writer_task = asyncio.create_task(excel_writer_worker(result_queue, output))
    else:
        writer_task = asyncio.create_task(writer_worker(result_queue, output, pretty))

    # Start failure writer task if requested
    failure_writer_task = None
    if failure_queue:
        failure_writer_task = asyncio.create_task(writer_worker(failure_queue, failures_output, pretty=False))

    # Helper function to check writer health before queue operations
    def check_writer_health():
        """Check if writer tasks have failed and raise exception if so."""
        if writer_task.done():
            exc = writer_task.exception()
            if exc:
                raise RuntimeError(f"Result writer task failed: {exc}") from exc
        if failure_writer_task and failure_writer_task.done():
            exc = failure_writer_task.exception()
            if exc:
                raise RuntimeError(f"Failure writer task failed: {exc}") from exc

    # Block detection setup (if enabled)
    pause_event = asyncio.Event()
    pause_event.set()  # Initially not paused
    block_detector = None
    detector_queue = None
    coordinator_task = None

    if block_detection:
        block_detector = BlockDetector(threshold=block_threshold, window_size=block_window)
        # Unbounded queue to prevent deadlock during pause (workers won't block on put)
        detector_queue = asyncio.Queue()
        coordinator_task = asyncio.create_task(
            block_detection_coordinator(
                detector_queue,
                pause_event,
                block_detector,
                block_action,
                block_auto_resume,
                quiet
            )
        )
        if not quiet:
            print(f"🛡️  Block detection enabled (threshold={block_threshold}, window={block_window}, action={block_action})", file=sys.stderr)

    # Progress tracking with ProgressTracker
    total_urls = len(urls)
    tracker = ProgressTracker(total_urls)
    progress_lock = asyncio.Lock()

    # Open checkpoint file for appending if requested
    checkpoint_handle = None
    if checkpoint_file:
        checkpoint_handle = open(checkpoint_file, "a", encoding="utf-8")

    # Per-domain rate limiting to prevent IP blocking
    # Track semaphores for each domain to limit concurrent requests per domain
    domain_semaphores: Dict[str, asyncio.Semaphore] = {}
    domain_sem_lock = asyncio.Lock()

    async def get_domain_semaphore(url: str) -> asyncio.Semaphore:
        """Get or create a semaphore for the domain to limit per-domain concurrency."""
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc

        async with domain_sem_lock:
            if domain not in domain_semaphores:
                domain_semaphores[domain] = asyncio.Semaphore(max_per_domain)
            return domain_semaphores[domain]

    async def apply_request_delay():
        """Apply configured delay with jitter between requests to avoid bot detection."""
        if delay > 0:
            # Add random jitter to delay to make timing less predictable
            actual_delay = delay + random.uniform(-jitter, jitter)
            # Ensure delay is never negative
            actual_delay = max(0.0, actual_delay)
            await asyncio.sleep(actual_delay)

    # Warn if TLS verification disabled
    if insecure and not quiet:
        print("⚠️  WARNING: TLS certificate verification disabled!", file=sys.stderr)

    try:
        async with httpx.AsyncClient(http2=True, headers={"user-agent": user_agent}, limits=limits, verify=not insecure) as client:
            sem = asyncio.Semaphore(concurrency)

            async def try_url_with_retries(url_to_try: str, original_url: str) -> Tuple[Optional[dict], Optional[int], Optional[Exception]]:
                """Try a URL with retry logic. Returns (result, status_code, exception).

                Args:
                    url_to_try: The URL to actually fetch (normalized or variation)
                    original_url: The exact original URL from input (preserved for result)

                Returns:
                    Tuple of (result_dict or None, status_code or None, exception or None)
                """
                last_exception = None
                last_status_code = None

                # Get domain semaphore to limit concurrent requests per domain
                domain_sem = await get_domain_semaphore(url_to_try)

                # Retry loop with exponential backoff
                for attempt in range(max_retries):
                    # Check pause before every attempt (block detection can trigger mid-retry)
                    try:
                        await asyncio.wait_for(pause_event.wait(), timeout=300)
                    except asyncio.TimeoutError:
                        print(f"⚠️  Retry loop timeout on pause - auto-resuming to prevent deadlock", file=sys.stderr)
                        pause_event.set()

                    try:
                        # Apply request delay with jitter (anti-blocking measure)
                        await apply_request_delay()

                        # Acquire domain semaphore to ensure max_per_domain limit
                        async with domain_sem:
                            # DEADLOCK FIX: Hard 30s timeout to prevent infinite hangs
                            # httpx timeout doesn't catch CLOSE_WAIT connections
                            res = await asyncio.wait_for(
                                process_url(original_url, url_to_try, client, render, validate),
                                timeout=30.0
                            )
                            # Success - return result with status code from result
                            status = res.get('http_status', 200)
                            return res, status, None

                    except Exception as e:
                        last_exception = e

                        # Extract HTTP status code from error message if present
                        error_msg = str(e).lower()

                        # Check for HTTP status codes that indicate blocking or rate limiting
                        if '429' in error_msg or 'too many requests' in error_msg:
                            # Rate limited - back off significantly and don't retry
                            print(f"Rate limited (429) on {url_to_try} - backing off 120s, skipping retries", file=sys.stderr)
                            await asyncio.sleep(120)
                            last_status_code = 429
                            break  # Don't retry on rate limiting

                        if '403' in error_msg or 'forbidden' in error_msg:
                            # Blocked/forbidden - don't retry
                            print(f"Forbidden (403) on {url_to_try} - likely blocked, skipping retries", file=sys.stderr)
                            last_status_code = 403
                            break  # Don't retry on blocks

                        # Check for transient errors that should be retried
                        is_transient = any(x in error_msg for x in ['timeout', 'connection', 'network', 'dns', '5'])

                        if attempt < max_retries - 1 and is_transient:
                            # Conservative exponential backoff: 5s, 15s, 45s (was 1s, 2s, 4s)
                            backoff = 5 * (3 ** attempt)
                            print(f"Retry {attempt + 1}/{max_retries} for {url_to_try} after {backoff}s (error: {e})", file=sys.stderr)
                            await asyncio.sleep(backoff)
                        else:
                            # Final attempt failed or non-transient error
                            break

                # All retries failed - return None result with failure info
                return None, last_status_code, last_exception

            async def worker(u: str):
                """Worker that processes a single URL with retry logic and optional URL variations

                Args:
                    u: The raw input URL from the file (before any normalization)
                """

                async with sem:
                    # Wait if paused (block detection) with timeout protection
                    try:
                        await asyncio.wait_for(pause_event.wait(), timeout=300)
                    except asyncio.TimeoutError:
                        # Just log timeout, don't mutate pause_event (let coordinator handle resume)
                        print(f"⚠️  Worker timeout on pause after 300s - coordinator should handle resume", file=sys.stderr)

                    # Normalize URL for fetching, but preserve original for tracking
                    normalized = normalize_url(u)

                    # Try normalized URL first, passing original u for result tracking
                    result, status_code, exception = await try_url_with_retries(normalized, u)

                    # Report attempt to block detector if enabled
                    if detector_queue:
                        await detector_queue.put({
                            'url': normalized,
                            'success': result is not None,
                            'status_code': status_code,
                            'exception': exception
                        })

                    if result is not None:
                        # Original URL succeeded
                        check_writer_health()  # Fail fast if writer died
                        await result_queue.put(result)

                        # Update progress and write to checkpoint
                        async with progress_lock:
                            tracker.completed += 1
                            tracker.success_count += 1
                            tracker.update_from_result(result)

                            if not quiet and (tracker.completed % progress_interval == 0 or tracker.completed == total_urls):
                                # Print progress based on selected style
                                if progress_style == "detailed":
                                    print(tracker.get_detailed_status(), file=sys.stderr)
                                elif progress_style == "json":
                                    print(tracker.get_json_status(), file=sys.stderr)
                                else:  # compact
                                    print(tracker.get_compact_status(), file=sys.stderr)

                            # Write URL to checkpoint file (move to thread to avoid blocking event loop)
                            if checkpoint_handle:
                                await asyncio.to_thread(checkpoint_handle.write, u + "\n")
                                await asyncio.to_thread(checkpoint_handle.flush)

                        return  # Success

                    # Normalized URL failed - try variations if enabled
                    if try_variations:
                        variations = generate_url_variations(normalized, max_variations)

                        if variations:
                            print(f"Normalized URL failed, trying {len(variations)} variation(s) for {u}", file=sys.stderr)

                        for variation_url in variations:
                            # Wait if paused before trying variation (with timeout protection)
                            try:
                                await asyncio.wait_for(pause_event.wait(), timeout=300)
                            except asyncio.TimeoutError:
                                # Just log timeout, don't mutate pause_event (let coordinator handle resume)
                                print(f"⚠️  Variation worker timeout on pause after 300s - coordinator should handle resume", file=sys.stderr)

                            result, var_status_code, var_exception = await try_url_with_retries(variation_url, u)

                            # Report variation attempt to block detector
                            if detector_queue:
                                await detector_queue.put({
                                    'url': variation_url,
                                    'success': result is not None,
                                    'status_code': var_status_code,
                                    'exception': var_exception
                                })

                            if result is not None:
                                # Variation succeeded
                                print(f"Success with variation: {variation_url} (original: {u})", file=sys.stderr)
                                check_writer_health()  # Fail fast if writer died
                                await result_queue.put(result)

                                # Update progress and write to checkpoint
                                async with progress_lock:
                                    tracker.completed += 1
                                    tracker.success_count += 1
                                    tracker.update_from_result(result)

                                    if not quiet and (tracker.completed % progress_interval == 0 or tracker.completed == total_urls):
                                        # Print progress based on selected style
                                        if progress_style == "detailed":
                                            print(tracker.get_detailed_status(), file=sys.stderr)
                                        elif progress_style == "json":
                                            print(tracker.get_json_status(), file=sys.stderr)
                                        else:  # compact
                                            print(tracker.get_compact_status(), file=sys.stderr)

                                    # Write original URL to checkpoint (not variation - move to thread)
                                    if checkpoint_handle:
                                        await asyncio.to_thread(checkpoint_handle.write, u + "\n")
                                        await asyncio.to_thread(checkpoint_handle.flush)

                                return  # Success with variation

                    # All attempts (original + variations) failed
                    async with progress_lock:
                        tracker.completed += 1
                        tracker.failure_count += 1

                        if not quiet and (tracker.completed % progress_interval == 0 or tracker.completed == total_urls):
                            # Print progress based on selected style
                            if progress_style == "detailed":
                                print(tracker.get_detailed_status(), file=sys.stderr)
                            elif progress_style == "json":
                                print(tracker.get_json_status(), file=sys.stderr)
                            else:  # compact
                                print(tracker.get_compact_status(), file=sys.stderr)

                    # Log error and put error result on both queues
                    attempted_urls = [normalize_url(u)]
                    if try_variations:
                        attempted_urls.extend(generate_url_variations(normalize_url(u), max_variations))

                    # Create failure result with same schema as success results
                    err = {
                        "original_url": u,                    # Raw input URL
                        "final_url": u,                       # Same as original (no successful fetch)
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "hubspot_detected": False,            # No detection occurred
                        "hubIds": [],                         # No Hub IDs found
                        "summary": {                          # Empty summary
                            "tracking": False,
                            "cmsHosting": False,
                            "features": {
                                "forms": False,
                                "chat": False,
                                "ctasLegacy": False,
                                "meetings": False,
                                "video": False,
                                "emailTrackingIndicators": False
                            },
                            "confidence": "weak"
                        },
                        "evidence": [],                       # No evidence
                        "headers": {},                        # No headers
                        "error": "Failed after all retry attempts" + (f" and {len(attempted_urls) - 1} URL variations" if try_variations else ""),
                        "attempts": max_retries,
                        "attempted_urls": attempted_urls
                    }
                    print(f"Failed after all attempts: {u} (tried {len(attempted_urls)} URL(s))", file=sys.stderr)
                    await result_queue.put(err)

                    if failure_queue:
                        check_writer_health()  # Fail fast if writer died
                        await failure_queue.put(err)

            # Process all URLs
            await asyncio.gather(*(worker(u) for u in urls))

            # Ensure we can shutdown even if paused
            if pause_event and not pause_event.is_set():
                print(f"⚠️  Shutdown while paused - resuming to allow cleanup", file=sys.stderr)
                pause_event.set()

            # Send poison pill to signal writer to stop
            await result_queue.put(None)
            if failure_queue:
                await failure_queue.put(None)

            # Send poison pill to block detector coordinator if enabled
            # Use put_nowait since queue might be unbounded but we want to avoid blocking
            if detector_queue:
                try:
                    detector_queue.put_nowait(None)
                except asyncio.QueueFull:
                    # Queue full (shouldn't happen with unbounded queue), cancel coordinator instead
                    if coordinator_task:
                        coordinator_task.cancel()

            # Wait for writer to finish
            await writer_task
            if failure_writer_task:
                await failure_writer_task

            # Wait for coordinator to finish if enabled
            if coordinator_task:
                await coordinator_task

            # Final summary
            if not quiet:
                print(f"\nCompleted: {total_urls} URLs ({tracker.success_count} succeeded, {tracker.failure_count} failed)", file=sys.stderr)
                if tracker.success_count > 0:
                    hs_pct = (tracker.hubspot_found / tracker.success_count * 100) if tracker.success_count > 0 else 0.0
                    print(f"HubSpot Found: {tracker.hubspot_found}/{tracker.success_count} ({hs_pct:.1f}%) | Unique Hub IDs: {len(tracker.hub_ids)}", file=sys.stderr)
                    print(f"Total Time: {tracker.format_time(tracker.get_elapsed_time())} | Average Rate: {tracker.get_rate():.1f} URL/s", file=sys.stderr)
    finally:
        # Close checkpoint file
        if checkpoint_handle:
            checkpoint_handle.close()

def parse_urls_from_file(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")]
