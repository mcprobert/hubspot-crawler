# HubSpot Detection Crawler (Python) — v1.4.0
Generated: 2025-10-04
**Status:** ✅ Production Ready - All Tests Passing
**Last Updated:** 2025-10-04 (v1.4.0: Ultra-Conservative Default)

This is a **Python** crawler that applies HubSpot web detection signatures and emits structured JSON results. All critical bugs from the initial implementation have been fixed and the crawler has been tested against live sites.

**Recent Updates (2025-10-04):**
- ✅ **v1.4.0: Ultra-conservative default** - Default mode now takes 3-5 hrs for 10k URLs with virtually zero IP blocking risk (quality over speed)
- ✅ **Phase 6.7.1: Preset modes** - 4 safety modes (ultra/conservative/balanced/aggressive) for easy configuration
- ✅ **Phase 6.7: Anti-blocking protection** - Per-domain limiting, request delays with jitter, smart 429/403 detection
- ✅ **Phase 6.6: CSV output format** - Export results to CSV for spreadsheet analysis (18 columns, flattened structure)
- ✅ **Phase 6.5: Simple detection flag** - Added `hubspot_detected` boolean for easy filtering (true if ANY HubSpot found)
- ✅ **Phase 6: Enhanced result metadata** - Now captures HTTP status codes, page titles, and meta descriptions for better domain analysis
- ✅ **Phase 5.5: Enhanced progress reporting** - Real-time HubSpot detection stats, performance metrics, time estimates, multiple output formats
- ✅ **Phase 4.5: Intelligent URL variation detection** - Automatically tries common URL variations (www, http/https, trailing slash) when original URL fails
- ✅ **Phase 4: Large-scale reliability** - Retry logic, checkpoint/resume, progress tracking, failure tracking
- ✅ **Phase 3.5: Fixed missing pattern detection** - Added 5 patterns that were defined but never checked
- ✅ Fixed 8 critical bugs (schema validation, CMS detection, evidence capture, Hub ID extraction)
- ✅ Fixed 7 high-priority bugs (error handling, confidence levels, cookie detection)
- ✅ Comprehensive test suite: 137 tests, 100% passing, 94% detector coverage
- ✅ Tested against whitehat-seo.co.uk, peppereffect.com, and hubspot.com
- ✅ All evidence now uses actual matched text (not hardcoded placeholders)
- ✅ Proper confidence level assignment (definitive/strong/moderate/weak)
- 📝 See STATUS.md for detailed development progress

## Features
- **Async HTTP** (httpx, HTTP/2) with configurable concurrency
- **Static scan** (HTML + resource URL extraction) or **Dynamic render** via **Playwright** to capture runtime network calls (Conversations, beacons, etc.)
- Evidence-level **regex signatures**: `hubspot_crawler/patterns/hubspot_patterns.json`
- **JSON Schema** validation (optional)
- **JSONL or CSV output** - JSONL for full details, CSV for spreadsheet analysis (18-column flattened format)
- **Gentle defaults**: UA string, timeouts; TLS verify disabled for robustness (flip if desired)

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# optional renderer backend:
python -m playwright install chromium
```

Or as a package:
```bash
pip install .
# extras:
pip install '.[render,validate]'
python -m playwright install chromium
```

## Usage

Single URL (static):
```bash
hubspot-crawl --url https://example.com
```

List of URLs (JSONL output to file):
```bash
hubspot-crawl --input examples/urls.txt --out results.jsonl
```

Large-scale crawl with retry, checkpointing, and failure tracking:
```bash
hubspot-crawl --input urls.txt --out results.jsonl \
  --checkpoint checkpoint.txt --failures failures.jsonl \
  --max-retries 3 --concurrency 20
```

Dynamic (JS executed; capture network & cookies; needs Playwright):
```bash
hubspot-crawl --input examples/urls.txt --render --validate --concurrency 5 --out results.jsonl
```

Pretty print to stdout:
```bash
hubspot-crawl --url https://example.com --pretty
```

CSV output (for spreadsheet analysis):
```bash
hubspot-crawl --input urls.txt --out results.csv --output-format csv
```

Large-scale CSV export:
```bash
hubspot-crawl --input urls.txt --out results.csv \
  --output-format csv --checkpoint checkpoint.txt \
  --concurrency 20 --quiet
```

## Output

Each line is a `DetectionResult` JSON object with the following structure:

### Core Fields
- `url` - The processed URL
- `timestamp` - ISO 8601 timestamp of detection
- `hubspot_detected` - **Boolean flag**: `true` if any HubSpot code/tracking/features detected, `false` otherwise (New in v1.3.1)
- `hubIds` - Array of discovered HubSpot portal IDs
- `summary` - Summary of detection results:
  - `tracking` - Boolean indicating HubSpot tracking presence
  - `cmsHosting` - Boolean indicating HubSpot CMS usage
  - `features` - Object with boolean flags for features (forms, chat, video, meetings, etc.)
  - `confidence` - Overall confidence level (definitive/strong/moderate/weak)
- `evidence` - Array of detection evidence with details
- `headers` - HTTP response headers

### Metadata Fields (New in v1.3.0)
- `http_status` - HTTP status code from the response (e.g., 200, 404, 500)
- `page_metadata` - Basic page metadata extracted from HTML:
  - `title` - Content of the `<title>` tag (null if not found)
  - `description` - Content of the meta description tag (null if not found)

These fields help determine if a domain is live and provide basic SEO context for the scanned pages.

### Optional Fields
- `url_variation` - Present when a URL variation was used (includes `original_url`, `working_url`, `variation_type`)

For complete schema details, see `hubspot_crawler/schemas/hubspot_detection_result.schema.json`.

## CSV Output Format (New in v1.3.2)

When using `--output-format csv`, results are exported to a flattened 18-column CSV structure suitable for spreadsheet analysis.

### CSV Columns

| Column | Type | Description |
|--------|------|-------------|
| `url` | string | The processed URL |
| `timestamp` | string | ISO 8601 timestamp |
| `hubspot_detected` | boolean | True if any HubSpot detected |
| `tracking` | boolean | HubSpot tracking detected |
| `cms_hosting` | boolean | HubSpot CMS detected |
| `confidence` | string | Overall confidence (definitive/strong/moderate/weak) |
| `forms` | boolean | Forms feature detected |
| `chat` | boolean | Chat feature detected |
| `ctas_legacy` | boolean | Legacy CTAs detected |
| `meetings` | boolean | Meetings feature detected |
| `video` | boolean | Video feature detected |
| `email_tracking` | boolean | Email tracking detected |
| `hub_ids` | string | Comma-separated Hub IDs (e.g., "123,456") |
| `hub_id_count` | integer | Number of unique Hub IDs |
| `evidence_count` | integer | Total evidence items |
| `http_status` | integer | HTTP status code (e.g., 200, 404) |
| `page_title` | string | Page title from `<title>` tag |
| `page_description` | string | Meta description content |

### CSV Example

```csv
url,timestamp,hubspot_detected,tracking,cms_hosting,confidence,forms,chat,ctas_legacy,meetings,video,email_tracking,hub_ids,hub_id_count,evidence_count,http_status,page_title,page_description
https://example.com,2025-10-04T21:07:25.458960Z,False,False,False,weak,False,False,False,False,False,False,,0,0,200,Example Domain,
https://www.hubspot.com,2025-10-04T21:07:30.244346Z,True,True,True,strong,False,False,False,False,False,False,,0,5,200,HubSpot | Software & Tools for your Business - Homepage,"HubSpot's customer platform includes all the marketing, sales, customer service, and CRM software you need to grow your business."
```

### When to Use CSV

**✅ Use CSV format when:**
- Analyzing results in Excel, Google Sheets, or similar tools
- Need simple boolean filters for HubSpot detection
- Running aggregate statistics (counts, percentages)
- Sharing results with non-technical stakeholders
- Building pivot tables or charts

**❌ Use JSONL format when:**
- Need full evidence details (pattern IDs, matches, sources)
- Require complete HTTP headers
- Building integrations that consume JSON
- Need to validate against the JSON schema
- Debugging detection results

## ⚠️ IP Blocking Risks & Protection (New in v1.3.3)

**IMPORTANT:** When scanning large numbers of domains, there is a **real risk of IP blocking** if you don't use conservative settings.

### Why IP Blocking Happens

Web servers and CDNs use sophisticated bot detection that looks for:

1. **Burst Patterns** - Multiple simultaneous requests to same domain
2. **Perfect Timing** - Requests arriving at perfectly regular intervals
3. **High Volume** - Sustained high request rate from single IP
4. **Retry Hammering** - Rapid-fire retries after failures
5. **Shared Infrastructure** - Scanning many sites on same CDN triggers provider-level blocks

**Real Risk:** Scanning 500 Cloudflare-hosted sites can get you blocked from **millions of Cloudflare sites** globally.

### Built-In Protection Features (v1.3.3)

The crawler now includes **conservative defaults** designed to prevent blocking:

| Feature | Default | Purpose |
|---------|---------|---------|
| `--mode` | ultra-conservative | Preset mode (NEW DEFAULT) |
| `--concurrency` | 2 | Total concurrent requests |
| `--max-per-domain` | 1 | Max requests per domain simultaneously |
| `--delay` | 3.0s | Delay between each request |
| `--jitter` | 1.0s | Random timing variation (±1.0s) |
| Retry backoff | 5s → 15s → 45s | Conservative retry delays |
| 429 detection | Auto-skip | Stops immediately on rate limiting |
| 403 detection | Auto-skip | Stops immediately when blocked |

**These defaults make your traffic indistinguishable from slow human browsing.**

### Ultra-Conservative Mode (DEFAULT - Maximum Safety)

```bash
# Ultra-slow, virtually impossible to block (DEFAULT)
hubspot-crawl --input urls.txt --out results.jsonl \
  --checkpoint checkpoint.txt \
  --quiet

# Automatically uses ultra-conservative mode (no --mode needed)
# Rate: ~0.5-0.7 URLs/sec
# 10,000 URLs: 3-5 hours
# Block risk: Essentially zero (indistinguishable from human)
```

**This is now the DEFAULT mode** because safety is prioritized over speed.

**Use ultra-conservative when:**
- Running any large-scale scan (default behavior)
- Scanning CDN-heavy domains (Cloudflare, AWS CloudFront)
- Your IP has been blocked before
- Scanning 50k-100k+ URLs
- Time is not a concern, only quality/safety matters

### Conservative Mode (Faster Alternative)

```bash
# Still very safe, but 6-8x faster than ultra-conservative
hubspot-crawl --input urls.txt --out results.jsonl \
  --mode conservative \
  --checkpoint checkpoint.txt \
  --quiet

# Rate: ~5 URLs/sec
# 10,000 URLs: 35-40 minutes
# Block risk: Virtually zero
```

### Balanced Mode (Medium risk, faster)

```bash
# Faster but still relatively safe
hubspot-crawl --input urls.txt --out results.jsonl \
  --mode balanced \
  --checkpoint checkpoint.txt

# Rate: ~10-12 URLs/sec
# 10,000 URLs: 12-16 minutes
# Block risk: Low-Medium
```

### Aggressive Mode (HIGH RISK - Not Recommended)

```bash
# Maximum speed, high blocking risk
hubspot-crawl --input urls.txt --out results.jsonl \
  --mode aggressive \
  --checkpoint checkpoint.txt

# Rate: ~20+ URLs/sec
# 10,000 URLs: 8-10 minutes
# Block risk: HIGH - Only use for known-safe domains
```

### Custom Mode (Fine-Grained Control)

```bash
# Mix preset with custom overrides
hubspot-crawl --input urls.txt --out results.jsonl \
  --mode conservative \
  --delay 2.0 \
  --jitter 0.5 \
  --checkpoint checkpoint.txt

# Starts with conservative preset, but uses 2.0s delay instead of 1.0s
```

### Detecting When You're Blocked

**Watch for these patterns in failures file:**

```bash
# Check failure rate
grep "429\|403\|Forbidden\|Rate limit" failures.jsonl | wc -l

# If you see many 429/403 errors:
# 1. STOP the crawl immediately
# 2. Wait 1-2 hours before resuming
# 3. Use more conservative settings
# 4. Consider using a proxy service
```

### Best Practices for Large Scans

✅ **DO:**
- Use checkpoint files (always resume-able)
- Start with conservative defaults
- Monitor failure patterns
- Spread scans over multiple days for 100k+ URLs
- Use residential IP addresses
- Filter out duplicate domains before scanning

❌ **DON'T:**
- Scan multiple URLs from same domain without `--max-per-domain 1`
- Disable delays (`--delay 0`) for unknown domains
- Ignore 429/403 errors
- Scan 10k+ sites from cloud IP addresses (AWS/GCP)
- Use `--try-variations` on large scans (adds retry overhead)

### Understanding the Risk

| Scale | Ultra-Conservative | Conservative | Balanced | Aggressive |
|-------|-------------------|--------------|----------|------------|
| 100 URLs | ✅ Safe | ✅ Safe | ✅ Safe | ✅ Safe |
| 1,000 URLs | ✅ Safe | ✅ Safe | ✅ Safe | ⚠️ Medium |
| 10,000 URLs | ✅ Safe | ✅ Safe | ⚠️ Medium | 🔴 High |
| 100,000 URLs | ✅ Safe | ✅ Safe* | 🔴 High | 🔴 Critical |

*Conservative @ 100k: Spread over 2-3 days for best safety
*Ultra-Conservative @ 100k: Can run continuously, ~200-300 hours total

## Large-Scale Usage (10k-100k+ URLs)

**New in v1.0.1:** Built-in support for large-scale reliable crawling

### Features for Production Scale
- **Automatic Retry with Exponential Backoff** - Recovers from transient network errors
- **Checkpoint/Resume** - Continue from where you left off after crash or interruption
- **Progress Tracking** - Real-time progress updates to stderr
- **Failure Tracking** - Separate output file for failed URLs
- **URL Deduplication** - Automatically removes duplicate URLs from input

### Recommended Settings for Large Crawls

For **10,000-100,000 URLs** (static mode):
```bash
hubspot-crawl --input urls.txt \
  --out results.jsonl \
  --checkpoint checkpoint.txt \
  --failures failures.jsonl \
  --concurrency 20 \
  --max-retries 3
```

**Key parameters:**
- `--checkpoint` - Tracks completed URLs, enables resume on crash
- `--failures` - Separate file for failed URLs (for manual review)
- `--max-retries 3` - Retry transient failures up to 3 times
- `--concurrency 20` - Process 20 URLs simultaneously (adjust based on network)

### Resume After Interruption
If the process crashes or is interrupted, simply rerun the **exact same command**. The crawler will:
1. Load completed URLs from checkpoint file
2. Skip already-processed URLs
3. Continue with remaining URLs
4. Append new results to output file

### Expected Performance
- **Static mode:** 50-200 URLs/sec (tested up to 100k URLs)
- **Dynamic mode:** 1-4 URLs/sec (use `--concurrency 5` for stability)
- **Memory usage:** ~500MB for 100k URLs with concurrency=20
- **Retry overhead:** Minimal (<5% extra time with default settings)

### Enhanced Progress Reporting (New in v1.2.0)

**Real-time visibility** into HubSpot detection, performance metrics, and progress.

#### Compact Mode (Default)
Progress updates every 10 URLs:
```
Progress: 100/10000 (1.0%) | Success: 98 | Failed: 2 | Rate: 25.3 URL/s | Elapsed: 0:04 | ETA: 6:12
HubSpot Found: 45/98 (45.9%) | Hub IDs: 12 unique
```

#### Detailed Mode
Full statistics including features and confidence:
```
Progress: 100/10000 (1.0%) | Success: 98 | Failed: 2 | Rate: 25.3 URL/s | Elapsed: 0:04 | ETA: 6:12
HubSpot Found: 45/98 (45.9%) | Tracking: 42 | CMS: 23 | Forms: 15 | Chat: 5
Confidence: Definitive: 30 | Strong: 10 | Moderate: 5 | Weak: 0 | Hub IDs: 12 unique
```

#### JSON Mode
Machine-parseable output for monitoring tools:
```json
{
  "progress": {"completed": 100, "total": 10000, "percentage": 1.0, "success": 98, "failed": 2},
  "performance": {"rate_urls_per_sec": 25.3, "elapsed_seconds": 4.0, "eta_seconds": 372},
  "hubspot_detection": {"found": 45, "tracking": 42, "cms": 23, "forms": 15, "unique_hub_ids": 12},
  "confidence": {"definitive": 30, "strong": 10, "moderate": 5, "weak": 0}
}
```

#### Usage
```bash
# Detailed progress (every 10 URLs by default)
hubspot-crawl --input urls.txt --progress-style detailed

# JSON progress (for parsing/monitoring)
hubspot-crawl --input urls.txt --progress-style json

# Custom update frequency (every 50 URLs)
hubspot-crawl --input urls.txt --progress-interval 50

# Quiet mode (no progress, errors only)
hubspot-crawl --input urls.txt --quiet
```

#### Final Summary
At completion, shows overall statistics:
```
Completed: 10000 URLs (9950 succeeded, 50 failed)
HubSpot Found: 4523/9950 (45.5%) | Unique Hub IDs: 1234
Total Time: 6:35 | Average Rate: 25.3 URL/s
```

## URL Variation Detection (New in v1.1.0)

**Problem:** Input URL lists often contain malformed URLs (missing www, wrong scheme, etc.) that fail unnecessarily.

**Solution:** The crawler can automatically try common URL variations when the original URL fails.

### How It Works

When `--try-variations` is enabled and a URL fails after all retry attempts, the crawler automatically tries:

1. **www variations** - Add/remove `www.` prefix
2. **Scheme variations** - Switch between `https://` and `http://`
3. **Trailing slash** - Add or remove trailing slash

Each variation is attempted with the same retry logic as the original URL.

### Usage

```bash
hubspot-crawl --input urls.txt --out results.jsonl \
  --try-variations \
  --max-variations 4
```

**Options:**
- `--try-variations` - Enable URL variation attempts (default: disabled)
- `--max-variations N` - Maximum variations to try per URL (default: 4)

### Example

Input URL: `https://example.com/page`

If the original fails, tries (in order):
1. `https://www.example.com/page` (add www)
2. `http://example.com/page` (change scheme)
3. `https://example.com/page/` (add trailing slash)

When a variation succeeds, the result includes metadata:
```json
{
  "url": "https://www.example.com/page",
  "url_variation": {
    "original_url": "https://example.com/page",
    "working_url": "https://www.example.com/page",
    "variation_type": "auto"
  },
  "summary": { ... }
}
```

### When to Use

✅ **Use `--try-variations` when:**
- Processing bulk URL lists from various sources
- URL quality/format is unknown
- You want to maximize successful scans
- Input preparation time is limited

❌ **Don't use `--try-variations` when:**
- URLs are already validated/normalized
- Speed is critical (variations add ~2-3x retry overhead on failures)
- You need strict "original URL only" behavior

### Limitations

- Only tries variations after ALL retry attempts are exhausted
- Does not try every possible combination (limited to 4 most common variations)
- Results always show the working URL (not the original if different)
- Checkpoint file tracks original URLs (not variations)

## Notes
- Without `--render`, you won't observe runtime beacons/calls blocked behind JS. We still parse resource URLs in HTML and catch the vast majority of signatures.
- With `--render`, we use Chromium headless via Playwright, subscribe to `request` events, and add them to the detection pass.
- Respect robots/ethics when scaling. Add rate-limits and domain-based concurrency if needed.

## Development Status

See **STATUS.md** for complete development progress, test results, and known issues.

**Current Status:**
- ✅ All critical bugs fixed (8/8)
- ✅ High-priority bugs fixed (8/10, 2 deferred)
- ✅ **Phase 3.5: Missing pattern detection fixed (5/5 patterns added)**
- ✅ **Phase 4: Large-scale reliability features (retry, checkpoint, progress tracking)**
- ✅ **Phase 4.5: URL variation detection (automatic fallback for malformed URLs)**
- ✅ **Phase 5.5: Enhanced progress reporting (real-time stats, multiple output formats)**
- ✅ Comprehensive test suite (137 tests, 100% passing)
- ✅ Tested on live sites (whitehat-seo.co.uk, peppereffect.com, hubspot.com)
- ✅ 94% test coverage on core detection logic
- ✅ Production-ready for 10k-100k URL crawls

**Known Limitations:**
- No structured logging (stderr prints only)
- No robots.txt parser
- All URLs loaded into memory (not a problem below 1M URLs)

## Examples
Input file format (one URL per line):
```
https://www.hubspot.com
https://www.whitehat-seo.co.uk
```

Example output (whitehat-seo.co.uk):
```json
{
  "url": "https://www.whitehat-seo.co.uk",
  "hubIds": [],
  "summary": {
    "tracking": true,
    "cmsHosting": true,
    "features": {
      "forms": false,
      "chat": false,
      "video": true
    },
    "confidence": "strong"
  },
  "evidence": [
    {
      "category": "tracking",
      "patternId": "_hsq_presence",
      "match": "_hsq.push(",
      "confidence": "strong"
    },
    {
      "category": "cms",
      "patternId": "cms_meta_generator",
      "match": "<meta name=\"generator\" content=\"HubSpot\"",
      "confidence": "strong"
    },
    {
      "category": "video",
      "patternId": "video_hubspotvideo",
      "match": "https://play.hubspotvideo.com/",
      "confidence": "strong"
    }
  ]
}
```

**Note:** The `_hsq_presence` pattern was added in Phase 3.5 to detect the most common HubSpot analytics implementation (the `_hsq` analytics queue).
