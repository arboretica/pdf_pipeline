"""
End-to-end test of the pdf_pipeline package.

Installs pdf_pipeline from the private GitHub repo, then runs all three
pipeline steps on a sample PDF file.

Usage:
    python test_pipeline.py \
        --google-api-key <GOOGLE_KEY> \
        --openai-api-key <OPENAI_KEY>

    # Or with env vars already set:
    python test_pipeline.py
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_URL = "git+https://github.com/mariamAbu/pdf_pipeline.git"
PDF_PATH = Path("/Users/mariam/CascadeProjects/nameholder-python-package/Codebase/Dow_esg_2020_corner_cases.pdf")

# Working directories (created next to the PDF)
WORK_DIR = PDF_PATH.parent / "pipeline_test_output"
MARKDOWN_DIR = WORK_DIR / "markdown_output"
TOC_JSON = WORK_DIR / "toc.json"
TOC_MD = WORK_DIR / "toc.md"
FAISS_DIR = WORK_DIR / "faiss_stores"


def run(cmd: list[str], **kwargs) -> None:
    """Run a command, printing it first, and abort on failure."""
    print(f"\n>>> {' '.join(cmd)}")
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(f"Command failed with exit code {result.returncode}")
        sys.exit(result.returncode)


# ---------------------------------------------------------------------------
# 0. Parse arguments
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="Test pdf_pipeline end-to-end.")
    parser.add_argument(
        "--google-api-key",
        default=os.environ.get("GOOGLE_API_KEY"),
        help="Google Gemini API key (or set GOOGLE_API_KEY env var)",
    )
    parser.add_argument(
        "--openai-api-key",
        default=os.environ.get("OPENAI_API_KEY"),
        help="OpenAI API key (or set OPENAI_API_KEY env var)",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip pip install (use if already installed)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # -----------------------------------------------------------------
    # 1. Install pdf_pipeline from GitHub
    # -----------------------------------------------------------------
    if not args.skip_install:
        print("\n" + "=" * 60)
        print("STEP 0: Installing pdf_pipeline from GitHub")
        print("=" * 60)
        run([sys.executable, "-m", "pip", "install", REPO_URL, "--quiet"])
    else:
        print("Skipping install (--skip-install)")

    # Verify import works
    print("\nVerifying import...")
    import pdf_pipeline
    print(f"  pdf_pipeline version: {pdf_pipeline.__version__}")

    # -----------------------------------------------------------------
    # 2. Prepare working directories
    # -----------------------------------------------------------------
    print(f"\nPDF file: {PDF_PATH}")
    if not PDF_PATH.exists():
        print(f"ERROR: PDF not found at {PDF_PATH}")
        sys.exit(1)

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    MARKDOWN_DIR.mkdir(parents=True, exist_ok=True)

    # Copy the PDF into a temp dir so marker-pdf can process it
    pdf_input_dir = WORK_DIR / "pdfs"
    pdf_input_dir.mkdir(parents=True, exist_ok=True)
    pdf_dest = pdf_input_dir / PDF_PATH.name
    if not pdf_dest.exists():
        shutil.copy2(PDF_PATH, pdf_dest)
    print(f"  PDF staged at: {pdf_dest}")

    # -----------------------------------------------------------------
    # 3. Step 1 — Convert PDF to Markdown
    # -----------------------------------------------------------------
    print("\n" + "=" * 60)
    print("STEP 1: Convert PDF to Markdown (marker-pdf)")
    print("=" * 60)

    convert_cmd = [
        "pdf-pipeline", "convert",
        "--pdf-dir", str(pdf_input_dir),
        "--output-dir", str(MARKDOWN_DIR),
        "--marker-only",  # Start with marker-only; Gemini enhancement below
    ]
    run(convert_cmd)

    # Optionally enhance with Gemini if key provided
    if args.google_api_key:
        print("\n--- Enhancing figures with Gemini ---")
        enhance_cmd = [
            "pdf-pipeline", "convert",
            "--pdf-dir", str(pdf_input_dir),
            "--output-dir", str(MARKDOWN_DIR),
            "--enhance-only",
            "--google-api-key", args.google_api_key,
        ]
        run(enhance_cmd)
    else:
        print("\n  [SKIP] No Google API key — skipping Gemini figure enhancement")

    # -----------------------------------------------------------------
    # 4. Step 2 — Extract TOC
    # -----------------------------------------------------------------
    print("\n" + "=" * 60)
    print("STEP 2: Extract Table of Contents")
    print("=" * 60)

    toc_cmd = [
        "pdf-pipeline", "extract-toc",
        "--markdown-dir", str(MARKDOWN_DIR),
        "--output-json", str(TOC_JSON),
        "--output-md", str(TOC_MD),
    ]
    run(toc_cmd)

    # Show the TOC JSON
    if TOC_JSON.exists():
        print(f"\n  TOC JSON written to: {TOC_JSON}")
        print(f"  TOC MD   written to: {TOC_MD}")

    # -----------------------------------------------------------------
    # 5. Step 3 — Chunk & Embed
    # -----------------------------------------------------------------
    print("\n" + "=" * 60)
    print("STEP 3: Chunk & Embed into FAISS")
    print("=" * 60)

    if args.openai_api_key:
        embed_cmd = [
            "pdf-pipeline", "chunk-embed",
            "--markdown-dir", str(MARKDOWN_DIR),
            "--toc-json", str(TOC_JSON),
            "--output-dir", str(FAISS_DIR),
            "--openai-api-key", args.openai_api_key,
        ]
        run(embed_cmd)
    else:
        print("  No OpenAI API key — running in dry-run mode (no embeddings)")
        embed_cmd = [
            "pdf-pipeline", "chunk-embed",
            "--markdown-dir", str(MARKDOWN_DIR),
            "--toc-json", str(TOC_JSON),
            "--output-dir", str(FAISS_DIR),
            "--openai-api-key", "placeholder",
            "--dry",
        ]
        run(embed_cmd)

    # -----------------------------------------------------------------
    # Done
    # -----------------------------------------------------------------
    print("\n" + "=" * 60)
    print("ALL STEPS COMPLETE")
    print("=" * 60)
    print(f"  Markdown output : {MARKDOWN_DIR}")
    print(f"  TOC JSON        : {TOC_JSON}")
    print(f"  TOC Markdown    : {TOC_MD}")
    print(f"  FAISS stores    : {FAISS_DIR}")


if __name__ == "__main__":
    main()
