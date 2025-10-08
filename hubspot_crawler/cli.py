
import argparse
import asyncio
import sys
from .crawler import run, parse_urls_from_file

def main():
    p = argparse.ArgumentParser(description="HubSpot web detection crawler (Python)")
    p.add_argument("--url", action="append", help="URL to scan (can be repeated)")
    p.add_argument("--input", help="Path to file with URLs (one per line)")

    # Preset modes for common use cases
    p.add_argument("--mode", choices=["ultra-conservative", "conservative", "balanced", "aggressive"],
                   help="Preset safety mode (overrides individual settings): "
                        "ultra-conservative (3-5 hrs/10k URLs, virtually zero block risk) [DEFAULT], "
                        "conservative (35-40 min/10k URLs, minimal risk), "
                        "balanced (12-16 min/10k URLs, low-medium risk), "
                        "aggressive (8-10 min/10k URLs, HIGH risk)")

    # Individual safety parameters (can override presets)
    p.add_argument("--concurrency", type=int, help="Concurrent fetches (default: depends on --mode)")
    p.add_argument("--delay", type=float, help="Delay between requests in seconds (default: depends on --mode)")
    p.add_argument("--jitter", type=float, help="Random jitter added to delay in seconds (default: depends on --mode)")
    p.add_argument("--max-per-domain", type=int, help="Maximum concurrent requests per domain (default: depends on --mode)")

    p.add_argument("--render", action="store_true", help="Use Playwright headless browser to execute JS and capture network")
    p.add_argument("--validate", action="store_true", help="Validate output against JSON Schema (requires jsonschema)")
    p.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification (DANGEROUS - allows MITM attacks)")
    p.add_argument("--user-agent", default="WhitehatHubSpotCrawler/1.0 (+https://whitehat-seo.co.uk)")
    p.add_argument("--out", help="Output file (JSONL, CSV, or Excel depending on --output-format)")
    p.add_argument("--output-format", choices=["jsonl", "csv", "xlsx"], default="jsonl", help="Output format: jsonl (default), csv, or xlsx (Excel)")
    p.add_argument("--pretty", action="store_true", help="Pretty-print JSON (only applies to jsonl format)")
    p.add_argument("--max-retries", type=int, default=3, help="Maximum retry attempts for failed requests (default: 3)")
    p.add_argument("--failures", help="Output file for failed URLs (JSONL)")
    p.add_argument("--checkpoint", help="Checkpoint file to track completed URLs (enables resume on crash)")
    p.add_argument("--try-variations", action="store_true", help="Try common URL variations (www, http/https, trailing slash) if original URL fails")
    p.add_argument("--max-variations", type=int, default=4, help="Maximum number of URL variations to try (default: 4)")
    p.add_argument("--progress-interval", type=int, default=10, help="Progress update frequency in URLs (default: 10)")
    p.add_argument("--progress-style", choices=["compact", "detailed", "json"], default="compact", help="Progress output style (default: compact)")
    p.add_argument("--quiet", action="store_true", help="Suppress progress output (errors only)")

    # Block detection parameters
    p.add_argument("--block-detection", action="store_true", help="Enable automatic IP blocking detection")
    p.add_argument("--block-threshold", type=int, default=5, help="Number of blocking failures to trigger alert (default: 5)")
    p.add_argument("--block-window", type=int, default=20, help="Sliding window size for tracking attempts (default: 20)")
    p.add_argument("--block-action", choices=["pause", "warn", "abort"], default="pause", help="Action when blocking detected: pause (interactive), warn (continue), abort (exit) (default: pause)")
    p.add_argument("--block-auto-resume", type=int, default=300, help="Auto-resume after N seconds in headless mode (default: 300, 0=never)")

    args = p.parse_args()

    urls = []
    if args.input:
        urls.extend(parse_urls_from_file(args.input))
    if args.url:
        urls.extend(args.url)
    if not urls:
        p.error("Provide --url or --input")

    # Deduplicate URLs while preserving order
    seen = set()
    deduped_urls = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            deduped_urls.append(url)

    if len(urls) != len(deduped_urls):
        print(f"Removed {len(urls) - len(deduped_urls)} duplicate URLs", file=sys.stderr)
    urls = deduped_urls

    # Apply preset mode if specified (can be overridden by individual parameters)
    mode = args.mode or "ultra-conservative"  # Default to ultra-conservative mode for maximum safety

    # Define preset configurations
    presets = {
        "ultra-conservative": {
            "concurrency": 2,
            "delay": 3.0,
            "jitter": 1.0,
            "max_per_domain": 1,
            "description": "Ultra-conservative (3-5 hrs/10k URLs, virtually zero block risk)"
        },
        "conservative": {
            "concurrency": 5,
            "delay": 1.0,
            "jitter": 0.3,
            "max_per_domain": 1,
            "description": "Conservative (35-40 min/10k URLs, minimal risk) [DEFAULT]"
        },
        "balanced": {
            "concurrency": 10,
            "delay": 0.5,
            "jitter": 0.2,
            "max_per_domain": 2,
            "description": "Balanced (16-18 min/10k URLs, low-medium risk)"
        },
        "aggressive": {
            "concurrency": 20,
            "delay": 0.0,
            "jitter": 0.0,
            "max_per_domain": 5,
            "description": "Aggressive (8-10 min/10k URLs, HIGH RISK)"
        }
    }

    preset = presets[mode]

    # Use preset values unless explicitly overridden
    concurrency = args.concurrency if args.concurrency is not None else preset["concurrency"]
    delay = args.delay if args.delay is not None else preset["delay"]
    jitter = args.jitter if args.jitter is not None else preset["jitter"]
    max_per_domain = args.max_per_domain if args.max_per_domain is not None else preset["max_per_domain"]

    # Validate numeric parameters
    if concurrency <= 0:
        p.error(f"--concurrency must be >= 1 (got {concurrency})")
    if delay < 0:
        p.error(f"--delay must be >= 0 (got {delay})")
    if jitter < 0:
        p.error(f"--jitter must be >= 0 (got {jitter})")
    if max_per_domain <= 0:
        p.error(f"--max-per-domain must be >= 1 (got {max_per_domain})")
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

    # Validate block detection settings
    if args.quiet and args.block_detection and args.block_action == "pause":
        p.error("--block-action pause requires interactive mode and cannot be used with --quiet.\n"
                "Use --block-action warn or --block-action abort instead for quiet/headless operation.")

    # Print mode selection if not quiet
    if not args.quiet:
        print(f"Using mode: {preset['description']}", file=sys.stderr)
        if args.concurrency is not None or args.delay is not None or args.jitter is not None or args.max_per_domain is not None:
            print(f"Custom overrides applied: concurrency={concurrency}, delay={delay}, jitter={jitter}, max-per-domain={max_per_domain}", file=sys.stderr)

    # Resume from checkpoint if requested
    completed_urls = set()
    if args.checkpoint:
        import os
        if os.path.exists(args.checkpoint):
            with open(args.checkpoint, "r", encoding="utf-8") as f:
                completed_urls = set(ln.strip() for ln in f if ln.strip())
            if not args.quiet:
                print(f"Loaded {len(completed_urls)} completed URLs from checkpoint {args.checkpoint}", file=sys.stderr)

            # Filter out already-completed URLs
            urls_before = len(urls)
            urls = [u for u in urls if u not in completed_urls]
            skipped = urls_before - len(urls)
            if skipped > 0 and not args.quiet:
                print(f"Skipping {skipped} already-completed URLs", file=sys.stderr)

        if len(urls) == 0:
            if not args.quiet:
                print("All URLs already completed!", file=sys.stderr)
            return

    asyncio.run(run(urls, concurrency=concurrency, render=args.render, validate=args.validate, user_agent=args.user_agent, output=args.out, output_format=args.output_format, pretty=args.pretty, max_retries=args.max_retries, failures_output=args.failures, checkpoint_file=args.checkpoint, try_variations=args.try_variations, max_variations=args.max_variations, progress_interval=args.progress_interval, progress_style=args.progress_style, quiet=args.quiet, delay=delay, jitter=jitter, max_per_domain=max_per_domain, block_detection=args.block_detection, block_threshold=args.block_threshold, block_window=args.block_window, block_action=args.block_action, block_auto_resume=args.block_auto_resume, insecure=args.insecure))

if __name__ == "__main__":
    main()
