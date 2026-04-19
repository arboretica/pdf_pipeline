"""
Command-line interface for pdf_pipeline.

Usage:
    pdf-pipeline convert   ...
    pdf-pipeline extract-toc ...
    pdf-pipeline chunk-embed ...
"""

import os

import click
from dotenv import load_dotenv

load_dotenv()


@click.group()
@click.version_option(package_name="pdf_pipeline")
def main():
    """pdf_pipeline — Convert PDFs to markdown, extract TOCs, chunk & embed."""


# -----------------------------------------------------------------------
# convert
# -----------------------------------------------------------------------

@main.command()
@click.option(
    "--pdf-dir", required=True, type=click.Path(exists=True, file_okay=False),
    help="Directory containing source PDF files.",
)
@click.option(
    "--output-dir", required=True, type=click.Path(file_okay=False),
    help="Directory where marker-pdf writes markdown output.",
)
@click.option(
    "--google-api-key", default=None,
    help="Google API key for Gemini. Falls back to GOOGLE_API_KEY env var.",
)
@click.option(
    "--gemini-model", default="gemini-2.0-flash", show_default=True,
    help="Gemini model to use for figure transcription.",
)
@click.option(
    "--marker-only", is_flag=True, default=False,
    help="Only run marker-pdf conversion, skip Gemini enhancement.",
)
@click.option(
    "--enhance-only", is_flag=True, default=False,
    help="Only run Gemini figure enhancement (assumes marker output exists).",
)
def convert(pdf_dir, output_dir, google_api_key, gemini_model, marker_only, enhance_only):
    """Step 1: Convert PDFs to markdown (marker-pdf + Gemini figure enhancement)."""
    from pdf_pipeline.convert import convert_pdfs_with_marker, enhance_figures_with_gemini

    if not enhance_only:
        click.echo("=== Running marker-pdf conversion ===")
        convert_pdfs_with_marker(pdf_dir, output_dir)

    if not marker_only:
        api_key = google_api_key or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise click.ClickException(
                "Google API key required. Provide --google-api-key or set GOOGLE_API_KEY env var."
            )
        click.echo("\n=== Enhancing figures with Gemini ===")
        enhance_figures_with_gemini(
            markdown_output_dir=output_dir,
            pdf_dirs=[pdf_dir],
            google_api_key=api_key,
            gemini_model=gemini_model,
        )


# -----------------------------------------------------------------------
# extract-toc
# -----------------------------------------------------------------------

@main.command("extract-toc")
@click.option(
    "--markdown-dir", required=True, type=click.Path(exists=True, file_okay=False),
    help="Directory containing markdown report sub-directories.",
)
@click.option(
    "--output-json", required=True, type=click.Path(dir_okay=False),
    help="Path for the output TOC JSON file.",
)
@click.option(
    "--output-md", default=None, type=click.Path(dir_okay=False),
    help="Optional path for a combined TOC markdown file.",
)
def extract_toc(markdown_dir, output_json, output_md):
    """Step 2: Extract table of contents from markdown reports."""
    from pdf_pipeline.extract_toc import process_all_reports, save_json_toc, save_combined_toc

    results = process_all_reports(markdown_dir)
    save_json_toc(results, output_json)

    if output_md:
        save_combined_toc(results, output_md)

    click.echo(f"\nProcessed {len(results)} reports:")
    for report_name, data in results.items():
        source = data.get("source", "unknown")
        label = "[existing TOC]" if source == "existing_toc" else "[from headings]"
        click.echo(f"  - {report_name}: {len(data['headings'])} entries {label}")


# -----------------------------------------------------------------------
# chunk-embed
# -----------------------------------------------------------------------

@main.command("chunk-embed")
@click.option(
    "--markdown-dir", required=True, type=click.Path(exists=True, file_okay=False),
    help="Directory containing markdown report sub-directories.",
)
@click.option(
    "--toc-json", required=True, type=click.Path(exists=True, dir_okay=False),
    help="Path to the TOC JSON file produced by extract-toc.",
)
@click.option(
    "--output-dir", required=True, type=click.Path(file_okay=False),
    help="Directory where FAISS vector stores will be saved.",
)
@click.option(
    "--openai-api-key", default=None,
    help="OpenAI API key. Falls back to OPENAI_API_KEY env var.",
)
@click.option(
    "--embedding-model", default="text-embedding-3-small", show_default=True,
    help="OpenAI embedding model name.",
)
@click.option(
    "--max-chunk-size", default=1500, show_default=True, type=int,
    help="Maximum chunk size in characters.",
)
@click.option(
    "--chunk-overlap", default=200, show_default=True, type=int,
    help="Overlap between chunks in characters.",
)
@click.option(
    "--skip", multiple=True,
    help="Report name(s) to skip. Can be specified multiple times.",
)
@click.option(
    "--dry", is_flag=True, default=False,
    help="Preview chunks without embedding or saving.",
)
def chunk_embed(
    markdown_dir, toc_json, output_dir, openai_api_key,
    embedding_model, max_chunk_size, chunk_overlap, skip, dry,
):
    """Step 3: Chunk markdown reports and embed into FAISS vector stores."""
    from pdf_pipeline.chunk_embed import run_chunk_embed

    api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise click.ClickException(
            "OpenAI API key required. Provide --openai-api-key or set OPENAI_API_KEY env var."
        )

    if dry:
        click.echo("DRY RUN — no embedding or FAISS save\n")

    run_chunk_embed(
        markdown_dir=markdown_dir,
        toc_json_path=toc_json,
        output_dir=output_dir,
        openai_api_key=api_key,
        embedding_model=embedding_model,
        max_chunk_size=max_chunk_size,
        chunk_overlap=chunk_overlap,
        skip_reports=list(skip),
        dry_run=dry,
    )
