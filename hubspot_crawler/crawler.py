
import asyncio
import re
import sys
import json
import time
import random
import urllib.parse
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

async def fetch_html(client: httpx.AsyncClient, url: str) -> Tuple[str, Dict[str, str], int]:
    """Fetch HTML with error handling. Returns (html, headers, status_code)"""
    try:
        r = await client.get(url, timeout=TIMEOUT, follow_redirects=True)
        r.raise_for_status()  # Raise on 4xx/5xx
        headers = {k: v for k, v in r.headers.items() if k and v}
        return r.text, headers, r.status_code
    except httpx.HTTPStatusError as e:
        # 4xx/5xx errors - still try to parse body if available
        headers = {k: v for k, v in e.response.headers.items() if k and v}
        status_code = e.response.status_code if e.response else 0
        return e.response.text if e.response else "", headers, status_code
    except (httpx.RequestError, httpx.TimeoutException) as e:
        # Network errors, DNS failures, timeouts
        raise RuntimeError(f"HTTP error fetching {url}: {str(e)}") from e

async def render_with_playwright(url: str, user_agent: str) -> Tuple[str, List[str], Dict[str,str]]:
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
        if resp:
            headers = {k: v for k, v in resp.headers.items()}
        # wait a bit for late beacons
        await page.wait_for_timeout(1500)
        await ctx.close()
        await browser.close()
    return html, network, headers

async def process_url(url: str, client: httpx.AsyncClient, render: bool, validate: bool) -> dict:
    """Process a URL and return detection results. Raises on fatal errors."""
    url = normalize_url(url)
    html = ""
    headers: Dict[str,str] = {}
    status_code = 0
    network_lines: List[str] = []

    try:
        if render and _HAS_PLAYWRIGHT:
            try:
                html, network_lines, headers = await render_with_playwright(url, client.headers.get("user-agent", DEFAULT_UA))
            except Exception as e:
                # Fall back to static if render fails
                print(f"Playwright render failed for {url}, falling back to static: {e}", file=sys.stderr)
                html, headers, status_code = await fetch_html(client, url)
                network_lines = extract_resource_urls(html, url)
        else:
            html, headers, status_code = await fetch_html(client, url)
            network_lines = extract_resource_urls(html, url)
    except Exception as e:
        # Fatal HTTP/network error - re-raise with context
        raise RuntimeError(f"Failed to fetch {url}: {str(e)}") from e

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

    result = make_result(url, ev, headers=headers, http_status=status_code, page_metadata=page_metadata)

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
        "url": result.get("url", ""),
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

    # CSV field names in order
    fieldnames = [
        "url", "timestamp", "hubspot_detected", "tracking", "cms_hosting", "confidence",
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

            # Flatten and write
            flat_row = flatten_result_for_csv(item)
            writer.writerow(flat_row)
            if f:
                f.flush()

            queue.task_done()
    finally:
        if f:
            f.close()

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

async def run(urls: List[str], concurrency: int = 2, render: bool = False, validate: bool = False, user_agent: str = DEFAULT_UA, output: Optional[str] = None, output_format: str = "jsonl", pretty: bool = False, max_retries: int = 3, failures_output: Optional[str] = None, checkpoint_file: Optional[str] = None, try_variations: bool = False, max_variations: int = 4, progress_interval: int = 10, progress_style: str = "compact", quiet: bool = False, delay: float = 3.0, jitter: float = 1.0, max_per_domain: int = 1):
    limits = httpx.Limits(max_connections=concurrency)

    # Create queue for results (bounded to prevent memory issues)
    result_queue = asyncio.Queue(maxsize=concurrency * 2)

    # Create queue for failures
    failure_queue = asyncio.Queue(maxsize=concurrency * 2) if failures_output else None

    # Start single writer task (choose format based on output_format parameter)
    if output_format == "csv":
        writer_task = asyncio.create_task(csv_writer_worker(result_queue, output))
    else:
        writer_task = asyncio.create_task(writer_worker(result_queue, output, pretty))

    # Start failure writer task if requested
    failure_writer_task = None
    if failure_queue:
        failure_writer_task = asyncio.create_task(writer_worker(failure_queue, failures_output, pretty=False))

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

    try:
        async with httpx.AsyncClient(http2=True, headers={"user-agent": user_agent}, limits=limits, verify=False) as client:
            sem = asyncio.Semaphore(concurrency)

            async def try_url_with_retries(url_to_try: str, original_url: str) -> Optional[dict]:
                """Try a URL with retry logic. Returns result on success, None on failure."""
                last_exception = None
                last_status_code = None

                # Get domain semaphore to limit concurrent requests per domain
                domain_sem = await get_domain_semaphore(url_to_try)

                # Retry loop with exponential backoff
                for attempt in range(max_retries):
                    try:
                        # Apply request delay with jitter (anti-blocking measure)
                        await apply_request_delay()

                        # Acquire domain semaphore to ensure max_per_domain limit
                        async with domain_sem:
                            res = await process_url(url_to_try, client, render, validate)
                            return res  # Success

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

                return None  # All retries failed

            async def worker(u: str):
                """Worker that processes a single URL with retry logic and optional URL variations"""

                async with sem:
                    # Try original URL first
                    result = await try_url_with_retries(u, u)

                    if result is not None:
                        # Original URL succeeded
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

                            # Write URL to checkpoint file
                            if checkpoint_handle:
                                checkpoint_handle.write(u + "\n")
                                checkpoint_handle.flush()

                        return  # Success

                    # Original URL failed - try variations if enabled
                    if try_variations:
                        variations = generate_url_variations(u, max_variations)

                        if variations:
                            print(f"Original URL failed, trying {len(variations)} variation(s) for {u}", file=sys.stderr)

                        for variation_url in variations:
                            result = await try_url_with_retries(variation_url, u)

                            if result is not None:
                                # Variation succeeded - add metadata
                                result["url_variation"] = {
                                    "original_url": u,
                                    "working_url": variation_url,
                                    "variation_type": "auto"
                                }
                                print(f"Success with variation: {variation_url} (original: {u})", file=sys.stderr)
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

                                    # Write original URL to checkpoint (not variation)
                                    if checkpoint_handle:
                                        checkpoint_handle.write(u + "\n")
                                        checkpoint_handle.flush()

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
                    attempted_urls = [u]
                    if try_variations:
                        attempted_urls.extend(generate_url_variations(u, max_variations))

                    err = {
                        "url": u,
                        "error": "Failed after all retry attempts" + (f" and {len(attempted_urls) - 1} URL variations" if try_variations else ""),
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "attempts": max_retries,
                        "attempted_urls": attempted_urls
                    }
                    print(f"Failed after all attempts: {u} (tried {len(attempted_urls)} URL(s))", file=sys.stderr)
                    await result_queue.put(err)

                    if failure_queue:
                        await failure_queue.put(err)

            # Process all URLs
            await asyncio.gather(*(worker(u) for u in urls))

            # Send poison pill to signal writer to stop
            await result_queue.put(None)
            if failure_queue:
                await failure_queue.put(None)

            # Wait for writer to finish
            await writer_task
            if failure_writer_task:
                await failure_writer_task

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
