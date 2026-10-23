"""
Command-line interface for pdf_pipeline.

Usage:
    pdf-pipeline convert   ...
    pdf-pipeline extract-toc ...
    pdf-pipeline chunk-embed ...
    pdf-pipeline smoke-test ...
"""

import logging
import os
import shutil
from pathlib import Path

import click
from dotenv import load_dotenv

from pdf_pipeline import config

load_dotenv()

logger = logging.getLogger("pdf_pipeline")

_VERBOSITY_LEVELS = [logging.WARNING, logging.INFO, logging.DEBUG]


@click.group()
@click.version_option(package_name="pdf-pipeline")
@click.option(
    "-v", "--verbose", count=True,
    help="Increase verbosity: -v for INFO logs, -vv for DEBUG logs.",
)
def main(verbose):
    """pdf_pipeline — Convert PDFs to markdown, extract TOCs, chunk & embed."""
    level = _VERBOSITY_LEVELS[min(verbose, len(_VERBOSITY_LEVELS) - 1)]
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    logger.debug("Verbosity set to %s (verbose=%d)", logging.getLevelName(level), verbose)


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
    help=f"Google API key for Gemini. Falls back to {config.GOOGLE_API_KEY_ENV} env var.",
)
@click.option(
    "--gemini-model", default=config.GEMINI_MODEL, show_default=True,
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
        api_key = google_api_key or os.environ.get(config.GOOGLE_API_KEY_ENV)
        if not api_key:
            raise click.ClickException(
                f"Google API key required. Provide --google-api-key or set "
                f"{config.GOOGLE_API_KEY_ENV} env var."
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
    help=f"OpenAI API key. Falls back to {config.OPENAI_API_KEY_ENV} env var. "
         f"Not required for --dry runs.",
)
@click.option(
    "--embedding-model", default=config.EMBEDDING_MODEL, show_default=True,
    help="OpenAI embedding model name.",
)
@click.option(
    "--max-chunk-size", default=config.MAX_CHUNK_SIZE, show_default=True, type=int,
    help="Maximum chunk size in characters.",
)
@click.option(
    "--chunk-overlap", default=config.CHUNK_OVERLAP, show_default=True, type=int,
    help="Overlap between chunks in characters.",
)
@click.option(
    "--skip", multiple=True,
    help="Report name(s) to skip. Can be specified multiple times.",
)
@click.option(
    "--dry", is_flag=True, default=False,
    help="Preview chunks without embedding or saving (no API key needed).",
)
def chunk_embed(
    markdown_dir, toc_json, output_dir, openai_api_key,
    embedding_model, max_chunk_size, chunk_overlap, skip, dry,
):
    """Step 3: Chunk markdown reports and embed into FAISS vector stores."""
    from pdf_pipeline.chunk_embed import run_chunk_embed

    if dry:
        # Keyless preview: chunks are built and printed, nothing is embedded.
        click.echo("DRY RUN — no embedding or FAISS save (no API key needed)\n")
        run_chunk_embed(
            markdown_dir=markdown_dir,
            toc_json_path=toc_json,
            output_dir=output_dir,
            openai_api_key=None,
            embedding_model=embedding_model,
            max_chunk_size=max_chunk_size,
            chunk_overlap=chunk_overlap,
            skip_reports=list(skip),
            dry_run=True,
        )
        return

    api_key = openai_api_key or os.environ.get(config.OPENAI_API_KEY_ENV)
    if not api_key:
        raise click.ClickException(
            f"OpenAI API key required. Provide --openai-api-key or set "
            f"{config.OPENAI_API_KEY_ENV} env var. (Hint: use --dry to preview "
            f"chunks without a key.)"
        )

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


# -----------------------------------------------------------------------
# smoke-test
# -----------------------------------------------------------------------

@main.command("smoke-test")
@click.option(
    "--workdir", default="./smoke_test_output", show_default=True,
    type=click.Path(file_okay=False),
    help="Working directory for smoke-test outputs.",
)
@click.option(
    "--with-convert", is_flag=True, default=False,
    help="Also run Step 1 (marker-pdf) on the bundled sample. Requires the "
         "`marker` CLI; OCR models are downloaded on first use.",
)
def smoke_test(workdir, with_convert):
    """Run the pipeline on bundled sample data — keyless (no API keys needed)."""
    from pdf_pipeline.chunk_embed import run_chunk_embed
    from pdf_pipeline.extract_toc import process_all_reports, save_json_toc

    samples_dir = Path(__file__).parent / "samples"
    md_source = samples_dir / "markdown_output"
    pdf_source = samples_dir / "sample_report.pdf"
    if not md_source.exists():
        raise click.ClickException(f"Bundled sample not found: {md_source}")

    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    md_dir = workdir / "markdown_output"
    if md_dir.exists():
        shutil.rmtree(md_dir)
    shutil.copytree(md_source, md_dir)
    click.echo(f"Sample markdown copied to: {md_dir}")

    if with_convert:
        if not pdf_source.exists():
            raise click.ClickException(f"Bundled sample PDF not found: {pdf_source}")
        from pdf_pipeline.convert import convert_pdfs_with_marker

        pdfs_dir = workdir / "pdfs"
        pdfs_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pdf_source, pdfs_dir / pdf_source.name)
        click.echo("\n=== Smoke test: Step 1 — convert (marker-pdf) ===")
        convert_pdfs_with_marker(str(pdfs_dir), str(md_dir))

    toc_json = workdir / "toc.json"
    click.echo("\n=== Smoke test: Step 2 — extract TOC ===")
    results = process_all_reports(str(md_dir))
    if not results:
        raise click.ClickException("Smoke test failed: no reports found in sample markdown.")
    save_json_toc(results, str(toc_json))

    click.echo("\n=== Smoke test: Step 3 — chunk & embed (dry run, keyless) ===")
    run_chunk_embed(
        markdown_dir=str(md_dir),
        toc_json_path=str(toc_json),
        output_dir=str(workdir / "faiss_stores"),
        openai_api_key=None,
        dry_run=True,
    )

    click.echo("\nSMOKE TEST PASSED")
    click.echo(f"  Working dir : {workdir}")
    click.echo(f"  TOC JSON    : {toc_json}")
