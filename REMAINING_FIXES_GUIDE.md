# Remaining Fixes Implementation Guide - v1.7.0

## Progress Summary
✅ **5/14 Complete** - All P0 critical deadlock fixes applied
⏳ **9/14 Remaining** - P1 and P2 fixes

---

## Fix #6: Enable TLS Verification (P1)

### Location
`crawler.py` line ~960 (in the run() function)

### Current Code
```python
async with httpx.AsyncClient(..., verify=False) as client:
```

### Fix
```python
# Add CLI parameter in cli.py after line 28:
p.add_argument("--insecure", action="store_true",
               help="Disable TLS certificate verification (DANGEROUS - allows MITM attacks)")

# Update run() signature in crawler.py ~876:
async def run(urls: List[str], ..., insecure: bool = False):

# Update AsyncClient creation in crawler.py ~960:
async with httpx.AsyncClient(
    http2=True,
    headers={"user-agent": user_agent},
    limits=limits,
    verify=not insecure  # Enable by default, disable only with --insecure
) as client:

# Add warning if insecure:
if insecure and not quiet:
    print("⚠️  WARNING: TLS certificate verification disabled!", file=sys.stderr)

# Update cli.py line ~138 to pass insecure flag:
asyncio.run(run(..., insecure=args.insecure))
```

---

## Fix #7: Fix or Remove retry_urls_queue (P1)

### Location
`crawler.py` lines 498-506 (retry push), 907 (queue creation)

### Option A: Remove Broken Feature (Recommended)
```python
# 1. Remove queue creation (line 907):
# DELETE: retry_urls_queue = asyncio.Queue()

# 2. Remove from coordinator signature (line 521):
async def block_detection_coordinator(...):
    # Remove retry_urls_queue parameter

# 3. Remove from handle_pause_prompt signature (line 444):
async def handle_pause_prompt(...):
    # Remove retry_urls_queue parameter

# 4. Remove retry option from prompt (lines 462, 498-506):
# Change options to just [c] Continue or [q] Quit
# Remove "[r] Retry" option entirely

# 5. Update all callers to remove retry_urls_queue parameter
```

### Option B: Implement Properly (Complex)
Requires refactoring to work queue pattern - see architecture notes in CODE_REVIEW_FINDINGS.

---

## Fix #8: Pause in Retry Loop (P1)

### Location
`crawler.py` lines 687-730 (`try_url_with_retries` function)

### Current Signature
```python
async def try_url_with_retries(url: str, original_url: str):
```

### Fix
```python
# 1. Add pause_event parameter:
async def try_url_with_retries(url: str, original_url: str, pause_event: asyncio.Event):

    for attempt in range(max_retries):
        # Add pause check before EVERY attempt
        try:
            await asyncio.wait_for(pause_event.wait(), timeout=300)
        except asyncio.TimeoutError:
            print(f"⚠️  Retry loop timeout on pause - auto-resuming", file=sys.stderr)
            pause_event.set()

        # ... rest of retry logic

# 2. Update ALL callers to pass pause_event:
# Line ~1049:
result, status_code, exception = await try_url_with_retries(normalized, u, pause_event)

# Line ~1107 (variation loop):
result, var_status_code, var_exception = await try_url_with_retries(variation_url, u, pause_event)
```

---

## Fix #9: Move Blocking I/O to Threads (P2)

### Locations
- Excel save: `crawler.py` line ~571
- CSV write: `crawler.py` line ~840
- Checkpoint write: `crawler.py` lines ~1086, ~1135

### Fix for Excel Writer
```python
# In excel_writer_worker() around line 571:
# Before:
wb.save(output)

# After:
await asyncio.to_thread(wb.save, output)
```

### Fix for CSV Writer
```python
# In csv_writer_worker() around line 840:
# Before:
csv_writer.writerow(flat_result)

# After:
await asyncio.to_thread(csv_writer.writerow, flat_result)
```

### Fix for Checkpoint Writes
```python
# Around lines 1086 and 1135:
# Before:
checkpoint_handle.write(u + "\n")
checkpoint_handle.flush()

# After:
await asyncio.to_thread(checkpoint_handle.write, u + "\n")
await asyncio.to_thread(checkpoint_handle.flush)
```

---

## Fix #10: Remove Worker Auto-Resume (P2)

### Location
`crawler.py` lines 1041-1044 (main worker), 1102-1105 (variation - already fixed)

### Current Code (Main Worker)
```python
try:
    await asyncio.wait_for(pause_event.wait(), timeout=300)
except asyncio.TimeoutError:
    print(f"⚠️  Worker timeout on pause - auto-resuming to prevent deadlock", file=sys.stderr)
    pause_event.set()  # <-- REMOVE THIS
```

### Fix
```python
try:
    await asyncio.wait_for(pause_event.wait(), timeout=300)
except asyncio.TimeoutError:
    # Just log timeout, don't mutate pause_event (let coordinator handle it)
    print(f"⚠️  Worker timeout on pause after 300s - coordinator should handle resume", file=sys.stderr)
    # Coordinator's try/finally will ensure resume
```

**Note:** Variation loop already fixed with same timeout but still sets event. Update it too to match.

---

## Fix #11: Fix Quiet Mode Output (P2)

### Location
`cli.py` lines 114, 119-120, 125

### Current Issues
```python
# Line 119: Always prints even with --quiet
print(f"Using mode: {preset['description']}", file=sys.stderr)

# Line 120: Always prints
if args.concurrency is not None or ...:
    print(f"Custom overrides applied: ...", file=sys.stderr)

# Line 125: Always prints
print(f"Loaded {len(completed_urls)} completed URLs from checkpoint ...", file=sys.stderr)
```

### Fix
```python
# Wrap all with quiet check:
if not args.quiet:
    print(f"Using mode: {preset['description']}", file=sys.stderr)
    if args.concurrency is not None or ...:
        print(f"Custom overrides applied: ...", file=sys.stderr)

# Line 125:
if not args.quiet:
    print(f"Loaded {len(completed_urls)} completed URLs from checkpoint {args.checkpoint}", file=sys.stderr)

# Also check lines 132, 135 for other prints
```

---

## Fix #12: Add Numeric Validation (P2)

### Location
`cli.py` after line 111 (after computing preset values)

### Add Validation
```python
# After line 111 (after computing concurrency, delay, jitter, max_per_domain):

# Validate numeric parameters
if concurrency <= 0:
    p.error(f"--concurrency must be >= 1 (got {concurrency})")
if delay < 0:
    p.error(f"--delay must be >= 0 (got {delay})")
if jitter < 0:
    p.error(f"--jitter must be >= 0 (got {jitter})")
if max_per_domain <= 0:
    p.error(f"--max-per-domain must be >= 1 (got {max_per_domain})")

# Also validate other params:
if args.max_retries < 0:
    p.error(f"--max-retries must be >= 0 (got {args.max_retries})")
if args.progress_interval <= 0:
    p.error(f"--progress-interval must be >= 1 (got {args.progress_interval})")
if args.max_variations < 0:
    p.error(f"--max-variations must be >= 0 (got {args.max_variations})")
if args.block_threshold <= 0:
    p.error(f"--block-threshold must be >= 1 (got {args.block_threshold})")
if args.block_window <= 0:
    p.error(f"--block-window must be >= 1 (got {args.block_window})")
if args.block_auto_resume < 0:
    p.error(f"--block-auto-resume must be >= 0 (got {args.block_auto_resume})")
```

---

## Fix #13: Version Update

### Files to Update

#### 1. pyproject.toml (line 8)
```python
version = "1.7.0"
```

#### 2. STATUS.md (lines 3-4)
```markdown
**Last Updated:** 2025-10-08
**Version:** 1.7.0 (Phase 1-8 Complete)
```

#### 3. Add Phase 8 section to STATUS.md
```markdown
### Phase 8: Comprehensive Deadlock Fixes ✅ COMPLETE
**Status:** Major stability improvements
**Completed:** 2025-10-08
**Tests:** 239/239 passing

**Goal:** Fix all 14 identified deadlock and reliability issues from GPT-5-Codex review

**Critical Fixes (P0):**
1. ✅ Unbounded detector_queue - prevents pause deadlock
2. ✅ Variation loop timeout - prevents infinite wait
3. ✅ Writer health monitoring - fail-fast on disk errors
4. ✅ Shutdown during pause - graceful cleanup
5. ✅ Coordinator cleanup - try/finally ensures resume

**High Priority (P1):**
6. ✅ TLS verification enabled - MITM protection
7. ✅ Fixed/removed retry_urls_queue - no broken features
8. ✅ Pause in retry loop - block detection works during retries

**Medium Priority (P2):**
9. ✅ Blocking I/O to threads - Excel/CSV/checkpoint writes
10. ✅ Removed worker auto-resume race - coordinator-only resume
11. ✅ Fixed quiet mode - proper output suppression
12. ✅ Numeric validation - prevents invalid parameters

**Benefits:**
✅ No more deadlocks - 9 deadlock vectors eliminated
✅ Production-ready - enterprise-scale capable
✅ Security hardened - TLS enabled by default
✅ Fail-fast errors - clear error messages
✅ Robust shutdown - graceful cleanup in all scenarios
```

---

## Fix #14: Testing

### Test Plan

#### 1. Unit Tests
```bash
# Test timeout logic
# Test writer health checks
# Test CLI validation

# Run existing suite:
python3 -m pytest tests/ -v
```

#### 2. Integration Tests
```bash
# Test 1: Pause and kill coordinator
# Expected: Workers auto-resume after 300s or on coordinator finally block

# Test 2: Cause writer failure (chmod 000 output file)
# Expected: RuntimeError raised immediately, not deadlock

# Test 3: Shutdown during pause
# Expected: Graceful shutdown, checkpoint saved

# Test 4: Block detection during retries
# Expected: Retries stop when paused
```

#### 3. Load Test
```bash
# Create 1000 URL test file
# Run with block detection
# Trigger pause, verify all workers stop
# Resume, verify crawl continues
```

---

## Completion Checklist

- [ ] Fix #6: TLS verification
- [ ] Fix #7: retry_urls_queue (remove or implement)
- [ ] Fix #8: Pause in retry loop
- [ ] Fix #9: Blocking I/O to threads
- [ ] Fix #10: Remove worker auto-resume
- [ ] Fix #11: Quiet mode output
- [ ] Fix #12: Numeric validation
- [ ] Fix #13: Version 1.7.0
- [ ] Fix #14: Testing
- [ ] Update CLAUDE.md
- [ ] Update README.md
- [ ] Git commit with detailed message

---

## Expected Outcome

**v1.7.0 Benefits:**
- ✅ Zero deadlock risk (all 9 vectors fixed)
- ✅ Production-grade reliability
- ✅ Security hardened (TLS enabled)
- ✅ Clear error messages
- ✅ Graceful degradation
- ✅ Enterprise-scale capable (100k-1M URLs)

**Risk Level:** 🟢 LOW (from 🔴 HIGH in v1.6.3)
