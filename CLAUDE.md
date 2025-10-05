# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based web crawler for detecting HubSpot integrations on websites. It applies regex-based signature matching to identify HubSpot tracking scripts, forms, chat, CMS hosting, and other features. The crawler supports both static HTML analysis and dynamic JavaScript rendering via Playwright.

**Status (2025-10-05):** Production ready for large-scale use (10k-100k URLs). All critical bugs fixed. Comprehensive test suite (218 tests, 100% passing).

**Recent Major Fixes:**
- **Phase 7.2 (2025-10-05):** Excel (.xlsx) export support
  - Added openpyxl optional dependency for Excel export
  - Handles commas and special characters in text fields without issues
  - Preserves data types (booleans, numbers, strings)
  - Bold headers in first row
  - 5 comprehensive tests for Excel output
  - Usage: `--output-format xlsx --out results.xlsx`
- **Phase 7.1 (2025-10-05):** HTTP error URL handling fix
  - Fixed bug where 4xx/5xx responses set `final_url` to normalized URL instead of `original_url`
  - Now `final_url = original_url` for all HTTP error responses (status >= 400)
  - Ensures proper dataset correlation for failed URLs
  - Added 2 tests for 4xx/5xx behavior
  - Updated `render_with_playwright()` to return status_code
- **Phase 7 (2025-10-05):** Dual URL tracking (original_url + final_url)
  - Tracks both input URL and final analyzed URL (after redirects/normalization)
  - Enables matching results back to original dataset
  - Breaking schema change: replaced single `url` field with `original_url` and `final_url`
  - Failure handling uses same schema structure as success results
  - 5 comprehensive tests for failure scenarios
  - CSV output updated with 19 columns (was 18)
- **Phase 5.5 (2025-10-04):** Enhanced progress reporting
  - Real-time HubSpot detection statistics (tracking, CMS, forms, chat, etc.)
  - Performance metrics (URLs/sec, elapsed time, ETA)
  - Multiple output formats (compact, detailed, JSON)
  - Configurable update frequency and quiet mode
  - 32 comprehensive tests for ProgressTracker
- **Phase 4.5 (2025-10-04):** Intelligent URL variation detection
  - Automatically tries common URL variations (www, http/https, trailing slash) when original URL fails
  - Opt-in feature via `--try-variations` flag
  - Each variation uses full retry logic
  - Results include metadata showing which variation worked
  - 26 comprehensive tests covering all variation types
- **Phase 4 (2025-10-04):** Large-scale reliability features for 10k-100k URLs
  - Automatic retry with exponential backoff (1s, 2s, 4s)
  - Checkpoint/resume capability (survive crashes)
  - Progress tracking (real-time monitoring)
  - Failure tracking (separate output for failed URLs)
  - URL deduplication (prevent duplicate processing)
- **Phase 3.5 (2025-10-04):** Added 5 missing pattern checks that were defined but never used
  - `_hsq_presence` - Analytics queue (CRITICAL - most common implementation)
  - `banner_helper` - Banner tracking
  - `url_params_hs` - URL parameter tracking (email/campaign)
  - `cms_host_hs_sites` - CMS domain detection
  - `tracking_script_any` - Fallback for scripts without id attribute
- Schema validation (importlib.resources)
- CMS detection logic (added /_hcms/ check)
- Evidence capture (actual matches, not hardcoded)
- Hub ID extraction (using capture groups)
- Confidence levels (proper if/elif/else logic)
- HTTP error handling (comprehensive try/except)
- Cookie detection (proper Set-Cookie parsing)
- Evidence deduplication
- Test suite (137 tests, 94% detector coverage)

See STATUS.md for complete development progress.

## Key Commands

### Setup
```bash
# Create virtual environment and install dependencies
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Install optional Playwright browser for dynamic rendering
python -m playwright install chromium
```

### Installation as package
```bash
# Basic install
pip install .

# With optional dependencies (validation + rendering + Excel)
pip install '.[render,validate,excel]'
python -m playwright install chromium

# Install specific optional features
pip install '.[excel]'     # Excel export support
pip install '.[validate]'  # Schema validation
pip install '.[render]'    # Playwright rendering
```

### Running the crawler
```bash
# Single URL (static analysis)
hubspot-crawl --url https://example.com

# Multiple URLs from file
hubspot-crawl --input examples/urls.txt --out results.jsonl

# With JavaScript rendering (requires Playwright)
hubspot-crawl --input examples/urls.txt --render --validate --concurrency 5 --out results.jsonl

# Pretty-print results to stdout
hubspot-crawl --url https://example.com --pretty

# Large-scale crawl with retry, checkpoint, and failure tracking (10k-100k URLs)
hubspot-crawl --input urls.txt --out results.jsonl \
  --checkpoint checkpoint.txt --failures failures.jsonl \
  --max-retries 3 --concurrency 20

# With URL variation detection (tries www, http/https, trailing slash on failures)
hubspot-crawl --input urls.txt --out results.jsonl \
  --try-variations --max-variations 4

# Enhanced progress reporting (detailed stats, every 10 URLs)
hubspot-crawl --input urls.txt --out results.jsonl \
  --progress-style detailed --progress-interval 10

# JSON progress output (for monitoring tools)
hubspot-crawl --input urls.txt --out results.jsonl \
  --progress-style json

# Quiet mode (no progress, errors only)
hubspot-crawl --input urls.txt --out results.jsonl --quiet

# Export to CSV format
hubspot-crawl --input urls.txt --out results.csv --output-format csv

# Export to Excel format (handles commas in fields, better data types)
hubspot-crawl --input urls.txt --out results.xlsx --output-format xlsx

# Excel export with all features
pip install '.[excel]'  # Install Excel support first
hubspot-crawl --input urls.txt --out results.xlsx --output-format xlsx \
  --checkpoint checkpoint.txt --max-retries 3 --concurrency 20
```

## Architecture

### Core Components

1. **Detector (`hubspot_crawler/detector.py`)**: Core detection logic that applies regex patterns to HTML and network data. Converts raw evidence into structured results with confidence levels.

2. **Crawler (`hubspot_crawler/crawler.py`)**: Orchestrates fetching and analysis. Supports two modes:
   - **Static**: Uses `httpx` to fetch HTML, extracts resource URLs with BeautifulSoup, applies detection patterns
   - **Dynamic**: Uses Playwright headless browser to capture runtime network calls, beacons, and dynamically-loaded content

3. **Patterns (`hubspot_crawler/patterns/hubspot_patterns.json`)**: Centralized JSON file containing all detection signatures as PCRE-style regex patterns. This is the single source of truth for what constitutes HubSpot presence.

4. **Schemas (`hubspot_crawler/schemas/`)**: JSON Schema definitions that validate output structure. Primary schema is `hubspot_detection_result.schema.json`.

5. **CLI (`hubspot_crawler/cli.py`)**: Command-line interface exposed as `hubspot-crawl`.

### Detection Flow

```
URL → Fetch (static or dynamic) → Extract HTML + Network Resources
→ Apply Patterns → Generate Evidence List → Summarize → DetectionResult JSON
```

### Evidence Categories
- `tracking`: Core HubSpot tracking scripts and analytics
  - **NEW (Phase 3.5):** `_hsq_presence` - Analytics queue (window._hsq)
  - **NEW (Phase 3.5):** `banner_helper` - Banner/notification tracking
  - **NEW (Phase 3.5):** `url_params_hs` - URL tracking parameters
  - **NEW (Phase 3.5):** `tracking_script_any` - Fallback pattern
- `forms`: Form loaders and submission endpoints
- `chat`: Live chat/conversations widget
- `ctas`: Legacy CTA system
- `meetings`: Meeting scheduler embeds
- `cms`: CMS hosting indicators (meta tags, hostnames)
  - **NEW (Phase 3.5):** `cms_host_hs_sites` - CMS domain detection in HTML
- `files`: File CDN references
- `video`: Video hosting
- `email`: Email tracking pixels/indicators
- `cookies`: HubSpot cookies in Set-Cookie headers
- `headers`: Server headers

### Confidence Levels
- **definitive**: Tracking loader script with Hub ID, official cookies, form submissions
- **strong**: Analytics includes, beacons, CMS-specific hostnames
- **moderate**: File CDN references without other signals, cookie mentions in HTML

## Important Implementation Details

### Hub ID Extraction
Hub IDs are extracted from:
- `js.hs-scripts.com/{HUB_ID}.js`
- `js.hs-analytics.net/analytics/{timestamp}/{HUB_ID}.js`

Multiple Hub IDs can be detected per page (indicates multi-portal setup or misconfiguration).

### CMS Hosting Detection
Requires strong evidence:
- Meta tag `generator=HubSpot`
- Class `hs_cos_wrapper` + path `/_hcms/`
- Hostname pattern `*.hs-sites.*`

File CDN alone (`hubspotusercontent-*`) is only **moderate** confidence since files can be hosted without CMS.

### CTA Legacy Detection
Requires **both**:
1. CTA loader script
2. `hbspt.cta.load(...)` call in HTML

One without the other is insufficient for definitive confidence.

### Static vs Dynamic Mode
- **Static** (default): Fast (50-200 URLs/sec), but misses runtime beacons and JS-loaded content
- **Dynamic** (`--render`): Slower (1-4 URLs/sec), captures late-loading scripts and network activity. Falls back to static on failure.

## Modifying Detection Signatures

To add or modify detection patterns:

1. Edit `hubspot_crawler/patterns/hubspot_patterns.json`
2. Use PCRE-style regex with proper escaping (`\\` for backslashes, `\.` for literal dots)
3. Patterns are compiled with `re.IGNORECASE | re.MULTILINE`
4. Use descriptive pattern IDs with category prefixes (`tracking_*`, `forms_*`, `chat_*`, etc.)
5. **IMPORTANT:** Add corresponding check in `detector.py` (see Phase 3.5 for examples)
6. Add test fixtures in `tests/conftest.py`
7. Add unit tests in appropriate `tests/test_detector_*.py` file
8. Run full test suite to verify: `python3 -m pytest tests/ -v`

Pattern naming convention: `{category}_{feature}_{variant}`
Example: `tracking_loader_script`, `forms_v2_loader`, `chat_conversations_api_eu1`

**Common Pitfall:** Adding patterns to JSON but forgetting to check them in `detector.py`. This was the root cause of the Phase 3.5 bug where 5 patterns were defined but never used.

## Output Format

Results are emitted as JSON conforming to `hubspot_detection_result.schema.json`:

```json
{
  "original_url": "example.com",
  "final_url": "https://www.example.com",
  "timestamp": "2025-10-05T12:34:56Z",
  "hubIds": [123456],
  "summary": {
    "tracking": true,
    "cmsHosting": false,
    "features": {
      "forms": true,
      "chat": false,
      "ctasLegacy": false,
      "meetings": false,
      "video": false,
      "emailTrackingIndicators": false
    },
    "confidence": "definitive"
  },
  "evidence": [...],
  "headers": {...},
  "url_variation": {
    "original_url": "https://example.com",
    "working_url": "https://www.example.com",
    "variation_type": "auto"
  }
}
```

**Important Schema Fields (v1.5.0):**
- `original_url`: The exact URL from the input file, before any normalization or transformations
- `final_url`: The final URL that was actually analyzed, after redirects and transformations
- `url_variation`: Optional field only present when `--try-variations` flag is used and a URL variation succeeded instead of the original URL

**Failure Handling:** When all URL attempts fail, both `original_url` and `final_url` are set to the input URL, and the result includes an `error` field with failure details.

## Configuration & Behavior

- TLS verification is disabled by default (`verify=False`) for robustness; re-enable if needed
- Default concurrency: controlled by `--concurrency` flag (impacts rate of requests)
- User-Agent: configurable via `--user-agent` flag
- Timeouts: built into httpx client
- Headers and cookies: Response headers inspected for Set-Cookie (names only, not values)

## Dependencies

Core:
- `httpx` (async HTTP/2 client)
- `beautifulsoup4` + `lxml` (HTML parsing)

Optional:
- `jsonschema` (output validation, enable with `--validate`)
- `playwright` (headless browser for `--render` mode)

## Related Documentation

See `HubSpot-Detection-Implementation-Guide-v1.2.md` for comprehensive implementation details, testing strategy, operational guidance, and roadmap.
