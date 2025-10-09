#!/bin/bash
# HubSpot Crawler v1.7.0 - Safe Restart Script
# Auto-generated: 2025-10-08

set -e  # Exit on any error

echo "================================================================"
echo "HubSpot Crawler v1.7.0 - Restart Script"
echo "================================================================"
echo ""

# Verify files exist
echo "Verifying data files..."
if [ ! -f "uk-companies-remaining-v1.7.0.txt" ]; then
    echo "❌ ERROR: uk-companies-remaining-v1.7.0.txt not found"
    exit 1
fi

if [ ! -f "checkpoint.txt" ]; then
    echo "❌ ERROR: checkpoint.txt not found"
    exit 1
fi

echo "✅ Input file: uk-companies-remaining-v1.7.0.txt ($(wc -l < uk-companies-remaining-v1.7.0.txt | xargs) URLs)"
echo "✅ Checkpoint: checkpoint.txt ($(wc -l < checkpoint.txt | xargs) completed)"
echo "✅ Failures:   failures.jsonl ($(wc -l < failures.jsonl 2>/dev/null | xargs || echo 0) failed)"
echo ""

# Progress tracking
echo "Progress Summary:"
echo "  Original:      999,999 URLs (461 duplicates)"
echo "  Unique:        999,538 URLs"
echo "  Completed:     78,863 URLs (7.9%)"
echo "  Failed:        28,386 URLs (2.8%)"
echo "  Remaining:     920,674 URLs (92.1%)"
echo ""

# Mode selection
echo "Select crawl mode:"
echo "  [1] Ultra-conservative (3-5 hrs/10k URLs, virtually zero block risk) [RECOMMENDED]"
echo "  [2] Conservative (35-40 min/10k URLs, minimal risk)"
echo "  [3] Balanced (12-16 min/10k URLs, low-medium risk)"
echo "  [4] Aggressive (8-10 min/10k URLs, HIGH risk)"
echo ""
read -p "Enter mode [1-4] (default: 1): " MODE_CHOICE
MODE_CHOICE=${MODE_CHOICE:-1}

case $MODE_CHOICE in
    1)
        MODE="ultra-conservative"
        CONCURRENCY=2
        DELAY=3.0
        JITTER=1.0
        MAX_PER_DOMAIN=1
        ;;
    2)
        MODE="conservative"
        CONCURRENCY=5
        DELAY=1.0
        JITTER=0.3
        MAX_PER_DOMAIN=1
        ;;
    3)
        MODE="balanced"
        CONCURRENCY=10
        DELAY=0.5
        JITTER=0.2
        MAX_PER_DOMAIN=2
        ;;
    4)
        MODE="aggressive"
        CONCURRENCY=20
        DELAY=0.0
        JITTER=0.0
        MAX_PER_DOMAIN=5
        ;;
    *)
        echo "Invalid mode, using ultra-conservative"
        MODE="ultra-conservative"
        ;;
esac

echo ""
echo "Using mode: $MODE"
echo ""

# Block detection settings
echo "Block detection settings:"
echo "  [1] Enabled with pause (interactive - allows IP change) [RECOMMENDED for large crawls]"
echo "  [2] Enabled with warning only (headless-friendly)"
echo "  [3] Disabled (not recommended for 900k+ URLs)"
echo ""
read -p "Enter choice [1-3] (default: 1): " BLOCK_CHOICE
BLOCK_CHOICE=${BLOCK_CHOICE:-1}

case $BLOCK_CHOICE in
    1)
        BLOCK_DETECTION="--block-detection --block-action pause --block-threshold 5 --block-window 20 --block-auto-resume 300"
        ;;
    2)
        BLOCK_DETECTION="--block-detection --block-action warn --block-threshold 5 --block-window 20"
        ;;
    3)
        BLOCK_DETECTION=""
        ;;
esac

# Output format
echo ""
echo "Output format:"
echo "  [1] JSONL (default, best for processing)"
echo "  [2] CSV (Excel-compatible)"
echo "  [3] Excel (.xlsx)"
echo ""
read -p "Enter choice [1-3] (default: 1): " OUTPUT_CHOICE
OUTPUT_CHOICE=${OUTPUT_CHOICE:-1}

case $OUTPUT_CHOICE in
    1)
        OUTPUT="results.jsonl"
        OUTPUT_FORMAT="jsonl"
        ;;
    2)
        OUTPUT="results.csv"
        OUTPUT_FORMAT="csv"
        ;;
    3)
        OUTPUT="results.xlsx"
        OUTPUT_FORMAT="xlsx"
        # Check if openpyxl is installed
        if ! python3 -c "import openpyxl" 2>/dev/null; then
            echo "⚠️  Excel support not installed. Installing openpyxl..."
            pip install 'openpyxl>=3.1.0'
        fi
        ;;
esac

# Backup existing output
if [ -f "$OUTPUT" ]; then
    BACKUP="$OUTPUT.backup-$(date +%Y%m%d-%H%M%S)"
    echo ""
    echo "⚠️  $OUTPUT exists, backing up to $BACKUP"
    mv "$OUTPUT" "$BACKUP"
fi

# Progress style
PROGRESS_STYLE="detailed"
PROGRESS_INTERVAL=10

echo ""
echo "================================================================"
echo "Starting crawler with settings:"
echo "================================================================"
echo "  Input:              uk-companies-remaining-v1.7.0.txt"
echo "  Output:             $OUTPUT ($OUTPUT_FORMAT)"
echo "  Mode:               $MODE"
echo "  Concurrency:        $CONCURRENCY"
echo "  Delay:              ${DELAY}s"
echo "  Jitter:             ${JITTER}s"
echo "  Max per domain:     $MAX_PER_DOMAIN"
echo "  Block detection:    $([ -n "$BLOCK_DETECTION" ] && echo "Enabled" || echo "Disabled")"
echo "  Checkpoint:         checkpoint.txt (resumes from 78,863 completed)"
echo "  Failures output:    failures.jsonl"
echo "  Progress:           Every $PROGRESS_INTERVAL URLs ($PROGRESS_STYLE)"
echo "  TLS verification:   Enabled (use --insecure to disable)"
echo ""
echo "  Estimated completion time:"
case $MODE_CHOICE in
    1) echo "    ~460 hours (19 days) for 920k URLs" ;;
    2) echo "    ~54 hours (2.3 days) for 920k URLs" ;;
    3) echo "    ~18 hours for 920k URLs" ;;
    4) echo "    ~12 hours for 920k URLs" ;;
esac
echo ""
echo "================================================================"
echo ""
read -p "Press Enter to start crawl (or Ctrl+C to cancel)..."
echo ""

# Run crawler
python3 -m hubspot_crawler.cli \
    --input uk-companies-remaining-v1.7.0.txt \
    --out "$OUTPUT" \
    --output-format "$OUTPUT_FORMAT" \
    --mode "$MODE" \
    --checkpoint checkpoint.txt \
    --failures failures.jsonl \
    --max-retries 3 \
    --try-variations \
    --max-variations 4 \
    --progress-style "$PROGRESS_STYLE" \
    --progress-interval "$PROGRESS_INTERVAL" \
    $BLOCK_DETECTION

echo ""
echo "================================================================"
echo "Crawl completed!"
echo "================================================================"
echo ""
echo "Results:"
echo "  Output:     $OUTPUT"
echo "  Checkpoint: checkpoint.txt"
echo "  Failures:   failures.jsonl"
echo ""
echo "Run analysis:"
echo "  wc -l checkpoint.txt failures.jsonl $OUTPUT"
echo ""
