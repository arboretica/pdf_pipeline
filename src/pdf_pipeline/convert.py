"""
Step 1: PDF to Markdown Conversion.

Uses marker-pdf for base conversion, then enhances figure-heavy pages
with Google Gemini vision transcription.
"""

import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Optional, Set

import pypdfium2 as pdfium
from google import genai
from google.genai import types


# ---------------------------------------------------------------------------
# Gemini client helpers
# ---------------------------------------------------------------------------

def _get_gemini_client(google_api_key: str) -> genai.Client:
    """Initialise and return a Google GenAI client."""
    return genai.Client(api_key=google_api_key)


def pdf_page_to_markdown_gemini(
    client: genai.Client,
    pdf_path: Path,
    model: str = "gemini-2.0-flash",
) -> str:
    """
    Convert a single-page PDF file to markdown using Google Gemini.

    Args:
        client: An initialised Google GenAI client.
        pdf_path: Path to a single-page PDF file.
        model: Gemini model to use.

    Returns:
        Markdown string of the page content.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    with open(pdf_path, "rb") as f:
        pdf_data = f.read()

    prompt = (
        "Convert this PDF document to well-formatted markdown.\n\n"
        "Instructions:\n"
        "- Preserve the document structure (headings, lists, tables)\n"
        "- Convert tables to markdown table format\n"
        "- Keep all text content accurate\n"
        "- Use appropriate heading levels (# ## ###)\n"
        "- Preserve any important formatting\n"
        "- Do not include page numbers or headers/footers\n"
        "- Output ONLY the markdown content, no explanations"
    )

    response = client.models.generate_content(
        model=model,
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part.from_bytes(data=pdf_data, mime_type="application/pdf"),
                    types.Part.from_text(text=prompt),
                ],
            )
        ],
    )

    return response.text


# ---------------------------------------------------------------------------
# Figure detection
# ---------------------------------------------------------------------------

def get_figure_pages(markdown_dir: Path) -> Set[int]:
    """Find all pages that have Figure jpeg files in a marker-pdf output directory."""
    figure_pages: Set[int] = set()
    for f in os.listdir(markdown_dir):
        match = re.match(r"_page_(\d+)_Figure_\d+\.jpeg", f)
        if match:
            figure_pages.add(int(match.group(1)))
    return figure_pages


# ---------------------------------------------------------------------------
# PDF page extraction
# ---------------------------------------------------------------------------

def extract_pdf_pages_as_single_pdf(
    pdf_path: Path,
    page_numbers: Set[int],
    output_dir: Path,
) -> Dict[int, Path]:
    """Extract individual pages from a PDF into separate single-page PDFs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf = pdfium.PdfDocument(str(pdf_path))
    pages_pdf: Dict[int, Path] = {}

    for page_number in sorted(page_numbers):
        if page_number < len(pdf):
            new_pdf = pdfium.PdfDocument.new()
            new_pdf.import_pages(pdf, [page_number])
            out_path = output_dir / f"page_{page_number}.pdf"
            new_pdf.save(str(out_path))
            pages_pdf[page_number] = out_path
        else:
            print(f"    Warning: Page {page_number} out of range (PDF has {len(pdf)} pages)")

    pdf.close()
    return pages_pdf


# ---------------------------------------------------------------------------
# Find matching PDF for a markdown directory
# ---------------------------------------------------------------------------

def find_pdf_for_directory(dir_name: str, pdf_dirs: list[Path]) -> Optional[Path]:
    """Find the corresponding PDF for a markdown output directory."""
    possible_names = [f"{dir_name}.pdf", dir_name]
    for pdf_dir in pdf_dirs:
        for name in possible_names:
            pdf_path = pdf_dir / name
            if pdf_path.exists():
                return pdf_path
    return None


# ---------------------------------------------------------------------------
# Single-directory processing
# ---------------------------------------------------------------------------

def process_directory(
    markdown_dir: Path,
    pdf_dirs: list[Path],
    gemini_client: genai.Client,
    gemini_model: str = "gemini-2.0-flash",
) -> bool:
    """
    Enhance a single marker-pdf output directory with Gemini transcriptions
    for pages that contain figures.

    Returns True on success, False on failure.
    """
    dir_name = markdown_dir.name
    print(f"\n{'=' * 60}")
    print(f"Processing: {dir_name}")

    # Find pages with figures
    figure_pages = get_figure_pages(markdown_dir)
    if not figure_pages:
        print("  No Figure files found, skipping")
        return True

    print(f"  Pages with figures: {sorted(figure_pages)}")

    # Find corresponding PDF
    pdf_path = find_pdf_for_directory(dir_name, pdf_dirs)
    if not pdf_path:
        print(f"  ERROR: No PDF found for {dir_name}")
        return False

    print(f"  PDF: {pdf_path}")

    # Extract figure pages as single-page PDFs
    page_images_dir = markdown_dir / "page_images"
    page_pdfs = extract_pdf_pages_as_single_pdf(pdf_path, figure_pages, page_images_dir)

    # Process each page with Gemini
    page_markdown: Dict[int, str] = {}
    for page_num, single_pdf_path in page_pdfs.items():
        print(f"    Processing page {page_num} with Gemini...")
        try:
            page_markdown[page_num] = pdf_page_to_markdown_gemini(
                gemini_client, single_pdf_path, model=gemini_model,
            )
            print(f"      Got {len(page_markdown[page_num])} chars")
        except Exception as e:
            print(f"      ERROR: {e}")
            continue

    # Read original markdown
    original_md_path = markdown_dir / f"{dir_name}.md"
    if not original_md_path.exists():
        print(f"  ERROR: Original markdown not found: {original_md_path}")
        return False

    with open(original_md_path, "r", encoding="utf-8") as f:
        updated_md = f.read()

    # Insert Gemini transcriptions before figure references
    for page_num, new_content in page_markdown.items():
        pattern = rf"!\[\]\(_page_{page_num}_Figure_\d+\.jpeg\)"
        replacement = (
            f"\n\n<!-- GEMINI TRANSCRIPTION FOR PAGE {page_num} START -->\n"
            f"{new_content}\n"
            f"<!-- GEMINI TRANSCRIPTION FOR PAGE {page_num} END -->\n\n"
        )
        match = re.search(pattern, updated_md)
        if match:
            insert_pos = match.start()
            updated_md = updated_md[:insert_pos] + replacement + updated_md[insert_pos:]

    # Save updated markdown
    updated_file = markdown_dir / f"{dir_name}_updated.md"
    with open(updated_file, "w", encoding="utf-8") as f:
        f.write(updated_md)

    print(f"  Saved: {updated_file}")
    return True


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------

def convert_pdfs_with_marker(pdf_dir: str, output_dir: str) -> None:
    """
    Convert all PDFs in *pdf_dir* to markdown using marker-pdf.

    This shells out to the ``marker`` CLI which must be installed.
    """
    import subprocess

    cmd = ["marker", str(pdf_dir), "--output_dir", str(output_dir)]
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def enhance_figures_with_gemini(
    markdown_output_dir: str,
    pdf_dirs: list[str],
    google_api_key: str,
    gemini_model: str = "gemini-2.0-flash",
) -> dict:
    """
    Walk all sub-directories in *markdown_output_dir*, detect figure pages,
    and enhance them with Gemini transcriptions.

    Returns a dict with 'success', 'failed', 'skipped' lists.
    """
    markdown_output_path = Path(markdown_output_dir)
    pdf_dir_paths = [Path(p) for p in pdf_dirs]
    client = _get_gemini_client(google_api_key)

    results: dict = {"success": [], "failed": [], "skipped": []}

    for subdir in sorted(markdown_output_path.iterdir()):
        if not subdir.is_dir():
            continue
        figure_pages = get_figure_pages(subdir)
        if figure_pages:
            success = process_directory(subdir, pdf_dir_paths, client, gemini_model)
            key = "success" if success else "failed"
            results[key].append(subdir.name)
        else:
            results["skipped"].append(subdir.name)

    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"  Success: {len(results['success'])} — {results['success']}")
    print(f"  Failed:  {len(results['failed'])} — {results['failed']}")
    print(f"  Skipped (no figures): {len(results['skipped'])}")

    return results
