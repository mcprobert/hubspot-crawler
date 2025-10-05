# HubSpot Web Detection Platform — Implementation & Maintenance Guide (v1.2)
**Date:** 2025-10-04  
**Owner:** Whitehat SEO (Engineering)  
**Maintainers:** Detection Platform Team

> This document fully describes the design and implementation of the HubSpot web‑detection stack delivered to you: the **JS/TS monorepo** (signatures, types, detector, CLI) and the **Python crawler** (static + optional headless). It’s intended for engineers who will maintain and extend the product.

---

## 0) TL;DR for busy humans
- **Signatures are data, not code.** We centralize file/URL/DOM patterns in JSON so multiple engines (TS & Python) can reuse them.
- **Evidence → Summary.** Engines gather *evidence* (regex/YARA matches, cookies, network calls), then compute boolean flags and a confidence level.
- **Two runtimes:**  
  - **Node/TS** (monorepo) for library & CI testing  
  - **Python** for large‑scale crawling (async HTTP, optional Playwright render)
- **Schemas everywhere.** Outputs conform to JSON Schemas and are validated in CI and (optionally) at runtime.
- **Add a new detection = update signatures + add table‑driven tests.** CI enforces schema correctness and expected flags.

---

## 1) Architecture Overview

### 1.1 Component Map

```
                           +---------------------------+
                           |  Patterns / Schemas (data)|
                           |  @whitehat/hubspot-signatures
                           |   - regex/hubspot_patterns.json
                           |   - schemas/*.json
                           |   - yara/*.yar
                           +-------------+-------------+
                                         |
                                         v
+----------------------+      +----------+-----------+      +--------------------+
|  Detector Library    |      |     CLI (Node)      |      |  Python Crawler    |
|  @whitehat/          |      |  @whitehat/cli      |      |  hubspot_crawler   |
|  hubspot-detector    |      |  hubspot-detect     |      |  hubspot-crawl     |
|  (TS/Node)           |      |  (local testing)    |      |  (scale crawling)  |
+----------+-----------+      +----------+----------+      +---------+----------+
           |                               |                          |
           v                               v                          v
    Evidence list                   JSON result stdout         JSONL results (schema)
           |                               |                          |
           +-------------->  Summary (flags & confidence)  <----------+
```

### 1.2 Repos & Packages
- **Monorepo (npm workspaces)** — *hubspot-monorepo-v1.2.zip*
  - `@whitehat/hubspot-signatures` — data‑only patterns & schemas
  - `@whitehat/hubspot-types` — TS interfaces mirroring schemas
  - `@whitehat/hubspot-detector` — minimal detector lib (HTML + network)
  - `@whitehat/hubspot-cli` — CLI wrapper for local scans/testing
- **Python crawler** — *hubspot-crawler-py-v1.0.zip*
  - `hubspot_crawler` package with `detector.py`, `crawler.py`, `patterns/`, `schemas/`, `cli.py`

---

## 2) Data Contracts (JSON Schemas)

### 2.1 DetectionResult
File: `schemas/hubspot_detection_result.schema.json` (present in both TS and Python bundles)

```json
{
  "url": "https://example.com",
  "timestamp": "2025-10-04T12:34:56Z",
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
  "evidence": [
    {
      "category": "tracking",
      "patternId": "tracking_loader_script",
      "match": "<script id=\"hs-script-loader\" src=\"https://js.hs-scripts.com/123456.js\">",
      "source": "html",
      "hubId": 123456,
      "confidence": "definitive",
      "context": "optional"
    }
  ],
  "headers": { "server": "nginx" }
}
```

### 2.2 Evidence Categories
- `tracking`, `forms`, `chat`, `ctas`, `meetings`, `cms`, `files`, `video`, `email`, `cookies`, `headers`

### 2.3 Confidence
- `definitive` | `strong` | `moderate` | `weak`  
  *We use deterministic rules (see §5.3).*

---

## 3) Signature Store

### 3.1 File: `regex/hubspot_patterns.json`
Format:
```json
{
  "version": "1.2",
  "generated": "{date}",
  "notes": "PCRE-style; case-insensitive",
  "patterns": {
    "tracking_loader_script": "<script...js\\.hs-scripts\\.com/(\\d+)\\.js...>",
    "analytics_core": "https?://js\\.hs-analytics\\.net/analytics/\\d+/(\\d+)\\.js",
    "...": "..."
  }
}
```

**Guidelines**
- **PCRE flavor** with escaping for `\\` and `.`; compile with `re.IGNORECASE | re.MULTILINE` (Py) / `/im` (JS).
- Group names sensibly (`forms_*`, `chat_*`, `cta_*`, `cms_*`).
- Prefer **explicit hosts** (`js.hs-scripts.com`) over generic wildcards.
- Keep regional variants (`-eu1`) where applicable.

### 3.2 YARA (optional)
- `yara/hubspot_web_html.yar` (HTML blobs)
- `yara/hubspot_network.yar` (network lines/HAR)
- Intended for offline scans (log archives, dumps). Not used at runtime by crawler.

---

## 4) Detector Libraries

### 4.1 Node/TS Detector (`@whitehat/hubspot-detector`)
Key functions (file: `src/index.ts`):
- `detectHtml(html): Evidence[]`
- `detectNetwork(lines: string): Evidence[]` — `lines` = newline‑delimited URLs
- `summarise(evidence): Summary`
- `runDetection(url, html, network): DetectionResult`

**Implementation details**
- Patterns: compiled from `@whitehat/hubspot-signatures` export.
- **Hub ID extraction:** from `js.hs-scripts.com/{HUB}.js` and `js.hs-analytics.net/analytics/{ts}/{HUB}.js`. Stored into `evidence[].hubId` and aggregated to `hubIds[]`.
- **CTA legacy:** requires both loader and `hbspt.cta.load(...)` call for definitive confidence.
- **Meetings:** either the embed JS or an iframe (`?embed=true`) is sufficient (strong).
- **CMS hosting:** meta `generator=HubSpot`, `hs_cos_wrapper` + `/_hcms/`, or `*.hs-sites.*` hostname (strong if host match).
- **Files CDN:** `hubspotusercontent-*` is **moderate** (files hosted ≠ CMS).

### 4.2 Python Detector (`hubspot_crawler/detector.py`)
Parity with TS implementation, same rules and confidence mapping.  
Exported helpers: `detect_html`, `detect_network`, `summarise`, `make_result`.

---

## 5) Confidence & Heuristics

### 5.1 Evidence Scoring Rules
- **Definitive:**
  - `id="hs-script-loader"` → `js.hs-scripts.com/{HUB}.js`
  - Presence of **HubSpot cookies** in headers (`hubspotutk`, `__hstc`, etc.)
  - Forms submission endpoint (`forms.hubspot.com/uploads/form/v2/...` or `api.hsforms.com/submissions/...`)
  - CTA legacy: loader **and** `hbspt.cta.load(...)`
- **Strong:**
  - Analytics include (`js.hs-analytics.net/analytics/.../{HUB}.js`)
  - Beacon `track.hubspot.com/__ptq.gif`
  - Meetings embed signals
  - CMS host `*.hs-sites.*`
- **Moderate:**
  - `hubspotusercontent-*` files without other CMS signals
  - Cookies **mentioned in HTML** (not set)
  - Weak URL params `_hs*`

### 5.2 Summary Derivation (pseudocode)
```text
tracking = any evidence.category == "tracking"
        OR any evidence.category == "cookies" AND match contains "hubspotutk"

cmsHosting = any evidence.category == "cms" AND confidence in {strong, definitive}

features = {
  forms: any "forms",
  chat: any "chat",
  ctasLegacy: any "ctas",
  meetings: any "meetings",
  video: any "video",
  emailTrackingIndicators: any "email"
}

confidence = if tracking AND any patternId == "tracking_loader_script" then "definitive"
             else if tracking then "strong"
             else "moderate"
```

### 5.3 Multiple Portals (multi‑HubID)
- We collect **all** Hub IDs from evidence.
- If `len(hubIds) > 1`, flag in ops/analytics. Some sites intentionally load multiple portals (subsidiaries), but it can signal misconfiguration.

---

## 6) Monorepo (JS/TS)

### 6.1 Packages
- `packages/signatures`  
  - Exposes `patterns` via `index.js` and raw JSON/Schema via subpath exports.
- `packages/types`  
  - `src/index.ts` exports `DetectionResult`, `Evidence`, etc.
- `packages/detector`  
  - `src/index.ts` (implementation), `tests/matrix.json`, `tests/matrix.test.ts`, `vitest.config.ts`
- `packages/cli`  
  - `src/cli.ts` — command `hubspot-detect`

### 6.2 Scripts
- `npm run lint` | `format` | `typecheck` | `test` | `build`
- CI workflow: `.github/workflows/ci.yml` executes the above on push/PR.

### 6.3 Adding or Changing a Signature
1. Edit `packages/signatures/regex/hubspot_patterns.json`.
2. Add a case in `packages/detector/tests/matrix.json`.
3. Update expected flags/Hub IDs.
4. Run `npm test`.  
5. Commit; CI enforces schema/tests.

---

## 7) Python Crawler

### 7.1 Modules
- `detector.py` — same logic as TS
- `crawler.py`
  - **Static path:**  
    - `httpx.AsyncClient(http2=True, verify=False)` → `GET` HTML  
    - Parse with **BeautifulSoup(lxml)**  
    - Extract `src/href` links from `script`, `link`, `img`, `iframe`, `a`  
    - Apply `detect_html` + `detect_network` (resource URLs)
  - **Dynamic path:** (optional)  
    - `playwright.chromium` headless; `page.on("request", ...)` to record URLs  
    - `page.goto(url, wait_until="load")` → `page.content()`  
    - Wait ~1.5s for late beacons  
    - Apply detection to HTML + captured network
  - **Headers & Cookies:** Inspect response headers for `Set-Cookie` (matches on official names).
  - **Resilience:** If headless fails, fall back to static.

- `cli.py` — exposes `hubspot-crawl`:
  ```
  hubspot-crawl --url <u> [--url <u>...] | --input urls.txt
                [--render] [--validate] [--concurrency N]
                [--user-agent "string"]
                [--out results.jsonl] [--pretty]
  ```

### 7.2 Concurrency & Backoff
- Uses `httpx` connection pool and an `asyncio.Semaphore` for **per‑process concurrency**.
- Add domain‑level limits if target sites rate‑limit aggressively (future improvement).

### 7.3 Output
- Each URL → one JSON object (optionally JSONL to a file).
- Optional schema validation via `jsonschema` if `--validate` is supplied.

---

## 8) Testing Strategy

### 8.1 TS: Table‑driven via Vitest + Ajv
- File: `packages/detector/tests/matrix.json`
- Test: `matrix.test.ts` runs each case →
  - Calls `runDetection()`
  - Validates against schema via Ajv
  - Asserts flags and Hub IDs

### 8.2 Python: Suggested tests (to add)
- Unit tests for `detect_html`, `detect_network` samples.
- Integration tests for `process_url` using a local test server (e.g., `pytest + respx` or `pytest-httpserver`) with fixtures that serve synthetic HTML and assets to emulate HubSpot signals.
- Optional HAR replay tests.

---

## 9) Operational Guidance

### 9.1 Scaling & Throughput
- **Static** paths can run at 50–200 URLs/sec per worker (network‑bound).
- **Dynamic** (Playwright) is heavier (1–4 URLs/sec per worker) depending on CPU & target pages.
- Run multiple processes or containers; shard input URL lists.

### 9.2 Politeness & Compliance
- Respect `robots.txt` if you plan to crawl beyond provided URLs. (Implementation stub recommended for v1.1.)
- Add a configurable **crawl delay** and per‑domain concurrency.
- **TLS verify:** currently `verify=False` to maximize success; consider enabling or using a trusted CA bundle in production.

### 9.3 Storage & Retention
- Default: evidence only; **no page bodies** persisted.  
- If you need to store HTML for debugging, store short‑term and **redact**/hash query parameters that may contain PII.

### 9.4 Observability
- Add structured logging (JSON) with fields: URL, phase, duration, http_status, error, evidence_counts.
- Metrics (suggested):
  - `crawl_urls_total`, `crawl_errors_total`, `avg_fetch_ms`, `avg_render_ms`
  - `detections_total` by category
- Optional: OpenTelemetry traces for `fetch` / `render` spans.

---

## 10) Security & Privacy

- **PII:** Do not log or persist full email addresses from inline JavaScript, if accidentally found. If you must store evidence excerpts, truncate at 300 chars (already implemented).
- **Cookies:** We only record **names** if seen in `Set-Cookie` (no values). Avoid storing cookie **values**.
- **Compliance:** If scanning third‑party sites, ensure you have contractual or legal basis. Prefer explicit opt‑in lists from clients.

---

## 11) Maintenance Plan

### 11.1 Versioning
- **Signatures**: semantic versioning in `regex/hubspot_patterns.json` `version`.  
  - `+patch` → regex tweak / false positive fix  
  - `+minor` → new patterns (backward compatible)  
  - `+major` → evidence semantics change
- **Packages**: monorepo packages use semver; CI tags on release branches.

### 11.2 Routine Tasks (Monthly)
- Refresh dependencies:
  - Node: typescript, vitest, ajv, eslint
  - Python: httpx, bs4, lxml, jsonschema, playwright
- Re‑run matrix; add **canary pages** from known HubSpot sites.
- Review HubSpot CDN/domain changes and update patterns.

### 11.3 Adding a New Feature Detector (example: “New CTA runtime”)
1. Capture real network & HTML samples.
2. Propose patterns:
   - Script host(s), iframe src, API endpoints, cookie names.
3. Add to `regex/hubspot_patterns.json` with clear `patternId` prefix.
4. Write a table‑driven test case (positive).
5. If needed, add a negative test (avoid false positives).
6. Update documentation (CHANGELOG, README).
7. Run CI, merge.

---

## 12) Roadmap (Recommended)

- **v1.3**
  - Robots.txt + sitemap discovery
  - Domain‑level concurrency & rate limits
  - Retry with exponential backoff and jitter
- **v1.4**
  - Storage plug‑ins: S3, GCS, SQLite, Parquet
  - Export to Kafka / PubSub stream for downstream processing
- **v1.5**
  - Canary monitoring: nightly job scanning ~20 “known good/bad” targets; alert on regressions
  - Optional **YARA** scanning for archives
- **v2.x**
  - Rule engine with **weights** instead of fixed confidence
  - Web UI dashboard (Next.js) for visualizing evidence and trends

---

## 13) Troubleshooting

- **No detections on SPA pages**  
  - Use `--render` to execute JS; increase wait time for late beacons.
- **Unexpected false positives (files CDN only)**  
  - Ensure policy requires >1 CMS signal for “CMS hosting”; or downgrade `hubspotusercontent-*` to informational.
- **Playwright errors**  
  - Install Chromium: `python -m playwright install chromium`.  
  - Try `--render` off to verify static path.
- **TLS failures / corporate proxies**  
  - Provide a CA bundle; or set `REQUESTS_CA_BUNDLE`/httpx `verify` path.

---

## 14) Appendix A — Commands

**Monorepo**
```bash
npm ci
npm run lint
npm run typecheck
npm test
npm run build
# CLI test
node packages/cli/dist/cli.js --url https://example.com --html examples/sample.html --network examples/sample_network.txt
```

**Python crawler**
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium   # optional, for --render
hubspot-crawl --input examples/urls.txt --out results.jsonl --render --validate
```

---

## 15) Appendix B — Example Annotated Result
```json
{
  "url": "https://example.com",
  "timestamp": "2025-10-04T12:34:56Z",
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
  "evidence": [
    {
      "category": "tracking",
      "patternId": "tracking_loader_script",
      "match": "<script id=\"hs-script-loader\" src=\"https://js.hs-scripts.com/123456.js\">",
      "source": "html",
      "hubId": 123456,
      "confidence": "definitive"
    },
    {
      "category": "forms",
      "patternId": "forms_v2_loader",
      "match": "https://js.hsforms.net/forms/v2.js",
      "source": "html",
      "confidence": "definitive"
    },
    {
      "category": "forms",
      "patternId": "forms_create_call",
      "match": "hbspt.forms.create({portalId:\"123456\", formId:\"a1b2...\"})",
      "source": "html",
      "confidence": "definitive"
    }
  ],
  "headers": { "server": "nginx" }
}
```

---

## 16) Appendix C — Signature Authoring Guidelines

- **Be precise:** Favor exact hostnames & endpoints over broad matches.
- **Anchor semantics:** If a pattern implies *presence of a feature*, set its baseline confidence (definitive/strong/moderate).
- **Region‑safe:** Include `eu1` variants where appropriate.
- **Escape properly:** Double‑escape backslashes in JSON.
- **Short matches:** Keep `evidence.match` excerpts short (<300 chars).
- **False positives:** Add a negative test when you tighten or broaden a regex.

---

## 17) Appendix D — File Index

- **Monorepo**
  - `packages/signatures/regex/hubspot_patterns.json`
  - `packages/signatures/schemas/*.json`
  - `packages/detector/src/index.ts`
  - `packages/detector/tests/matrix.json`
  - `packages/cli/src/cli.ts`
- **Python**
  - `hubspot_crawler/patterns/hubspot_patterns.json`
  - `hubspot_crawler/schemas/*.json`
  - `hubspot_crawler/detector.py`
  - `hubspot_crawler/crawler.py`
  - `hubspot_crawler/cli.py`

---

### Final word
This stack is intentionally simple and boring: **data‑driven signatures**, schema‑validated outputs, and table‑driven tests. Keep it that way and you’ll avoid 90% of the maintenance pain. When HubSpot changes something (they will), it’s a one‑file diff plus a matrix test, not a rewrite.
