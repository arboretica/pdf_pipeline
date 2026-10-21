# Contributing Guide

Welcome! Thanks for taking an interest in improving **pdf_pipeline** — a three-step pipeline that
1) converts PDF reports to markdown (marker-pdf + Google Gemini figure transcription),
2) extracts or builds a table of contents per report, and
3) chunks and embeds the markdown into per-report FAISS vector stores.

This guide explains how to set up your environment, the coding style we use, how to propose changes, and where in the codebase to make them.

---

## Table of contents
- [Code of Conduct](#code-of-conduct)
- [Project overview](#project-overview)
- [Getting started](#getting-started)
- [Running the pipeline](#running-the-pipeline)
- [How to contribute](#how-to-contribute)
- [Coding standards](#coding-standards)
- [Where to make changes](#where-to-make-changes)
- [Testing & verification](#testing--verification)
- [Security](#security)
- [Pull request checklist](#pull-request-checklist)
- [Release notes](#release-notes)
- [Authors](#authors)

---

## Code of Conduct

Be kind, respectful, and constructive. We follow the spirit of the [Contributor Covenant](https://www.contributor-covenant.org/).
Harassment or disrespectful conduct is not tolerated.

---

## Project overview

**High-level flow**

- **Step 1** (`src/pdf_pipeline/convert.py`): runs `marker-pdf` over every PDF in `--pdf-dir`, then scans the output for figure pages and enhances them with Gemini vision transcription (`--marker-only` / `--enhance-only` toggle the two halves).
- **Step 2** (`src/pdf_pipeline/extract_toc.py`): for each report directory, reuses an existing TOC section if the document has one (≥ 3 entries), otherwise builds a TOC from the markdown heading hierarchy; saves JSON (and optionally combined markdown).
- **Step 3** (`src/pdf_pipeline/chunk_embed.py`): loads the TOC JSON, splits each report into TOC-guided sections, separates tables from text, recursively splits oversized chunks, embeds with OpenAI, and saves one FAISS index per report.
- **CLI** (`src/pdf_pipeline/cli.py`): a `click` group exposing `convert`, `extract-toc`, `chunk-embed`, and a keyless `smoke-test` command.
- **Config** (`src/pdf_pipeline/config.py`): every tunable (model names, chunk sizes, env-var names) lives here; CLI flags override.

**Key outputs**
- `markdown_output/<report>/<report>.md` — marker-pdf conversion per report (plus `<report>_updated.md` after Gemini enhancement)
- `toc.json` — structured TOC per report, consumed by Step 3
- `faiss_stores/<report>/` — one FAISS vector store per report

---

## Getting started

### Prerequisites
- **Python** 3.10+
- A virtual environment tool (`venv` or `conda`)
- `poppler-utils` if you use the optional `pdf2image` dependency (`brew install poppler` on macOS, `apt install poppler-utils` on Debian/Ubuntu)
- API keys:
  - **GOOGLE_API_KEY** (for Step 1 Gemini figure enhancement)
  - **OPENAI_API_KEY** (for Step 3 embeddings)

### Setup
```bash
git clone https://github.com/arboretica/pdf_pipeline.git
cd pdf_pipeline

# Create and activate a virtual environment
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install runtime + dev deps (pytest included via the [dev] extra)
pip install -U pip
pip install -e ".[dev]"

# Provide secrets via environment (recommended) or a .env file
cp .env.example .env   # then edit
```
> The CLI auto-loads `.env` if present; otherwise pass keys as flags when running.

---

## Running the pipeline

```bash
pdf-pipeline convert     --pdf-dir ./pdfs --output-dir ./md_output --google-api-key $GOOGLE_API_KEY
pdf-pipeline extract-toc --markdown-dir ./md_output --output-json ./toc.json
pdf-pipeline chunk-embed --markdown-dir ./md_output --toc-json ./toc.json --output-dir ./faiss_stores --openai-api-key $OPENAI_API_KEY
```

Increase verbosity with `-v` (INFO) or `-vv` (DEBUG) **before** the subcommand:

```bash
pdf-pipeline -vv chunk-embed --markdown-dir ./md_output --toc-json ./toc.json --output-dir ./faiss_stores --dry
```

`--dry` previews chunks without embedding or saving — it works **without an API key**.

For a keyless end-to-end check on the bundled sample data, run:

```bash
pdf-pipeline smoke-test
```

---

## How to contribute

1. **Open an issue** describing the problem/enhancement. Propose a minimal plan of change.
2. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feat/<short-slug>
   ```
3. **Implement & self-review** (see standards below).
4. **Add/adjust tests** and run the checks under [Testing & verification](#testing--verification).
5. **Submit a PR** that references the issue and explains *what changed* and *why*.
6. Engage with review comments and iterate quickly.

**Commit messages**: Prefer Conventional Commits (e.g., `feat: add csv toc input`, `fix: guard empty headings`).

---

## Coding standards

- **Type hints everywhere** the codebase already uses them; keep new code typed.
- **Logging over print for diagnostics**: user-facing output uses `print`/`click.echo`; diagnostic detail goes through `logging` and honors `-v`/`-vv`. Never log secrets.
- **Config first**: place tunables in `src/pdf_pipeline/config.py` (model names, chunk sizes, env-var names); never hardcode defaults in CLI options or function signatures.
- **Docstrings** for public functions; short comments for non-obvious heuristics.
- **Small, pure functions** where possible. Keep I/O at the edges.
- **Avoid leaking secrets** in code, tests, or sample snippets. Read keys from env/`.env`/CLI flags, in that precedence order.
- **External calls**: catch exceptions and log succinctly; do not retry aggressively against quota-limited APIs.
- **Markdown splitting heuristics**: changes to TOC detection or chunking must come with unit tests in `tests/` (the existing `test_extract_toc.py` shows the pattern — stdlib-only fixtures, no network).

---

## Where to make changes

### Change defaults / tunables (chunk size, models, env-var names)
- Edit `src/pdf_pipeline/config.py`. CLI options in `cli.py` read their defaults from there — keep it that way.

### Improve **PDF conversion** (Step 1)
- `src/pdf_pipeline/convert.py`: marker invocation, figure-page detection, Gemini prompting and markdown insertion.
- The Gemini figure enhancement is skipped entirely with `--marker-only`.

### Improve **TOC extraction** (Step 2)
- `src/pdf_pipeline/extract_toc.py`: TOC section detection patterns, heading parsing, output serialization.
- Add cases to `tests/test_extract_toc.py` when touching detection logic.

### Improve **chunking & embedding** (Step 3)
- `src/pdf_pipeline/chunk_embed.py`: section splitting, table separation, recursive chunking, FAISS persistence.
- `--dry` (chunk preview without embedding) must keep working without an API key — preserve that invariant.

### Add / change **CLI flags**
- `src/pdf_pipeline/cli.py`. Use `click` options with `show_default=True` and defaults sourced from `config.py`.
- Update `README.md` flag tables when flags change.

---

## Testing & verification

Run the full suite:

```bash
pytest tests/ -v
```

Keyless end-to-end check on the bundled sample:

```bash
pdf-pipeline smoke-test
```

**What to verify before opening a PR**
- New unit tests for any change to TOC detection, chunking, or config defaults.
- `pdf-pipeline --help` still lists all subcommands; `-v`/`-vv` parse.
- `chunk-embed --dry` works without an API key; without `--dry` it still requires one and fails with a clear message.
- `pytest tests/ -v` passes and `pdf-pipeline smoke-test` reports PASS.

**Suggested unit-test areas (PRs welcome)**
- `extract_toc.find_existing_toc` edge cases (table-style TOCs, numbered entries, bold headings)
- `chunk_embed._infer_depth_from_title` numbering patterns (Roman numerals, dotted numbering)
- `chunk_embed.separate_tables` mixed text/table content
- CLI wiring (`tests/test_cli.py` uses `click.testing.CliRunner`)

---

## Security

- **Do not commit** API keys, auth cookies, or personally identifying information.
- See [SECURITY.md](SECURITY.md) for how to report vulnerabilities — please use private GitHub Security Advisories, not public issues.
- Only run the pipeline on documents from sources you trust.

---

## Pull request checklist

- [ ] Code is typed, documented, and follows the logging conventions above.
- [ ] No secrets in code, tests, or logs.
- [ ] Configurable values live in `config.py` (not hardcoded in CLI or modules).
- [ ] Added/updated tests; `pytest tests/ -v` and `pdf-pipeline smoke-test` pass.
- [ ] Updated `README.md` if behavior/flags/outputs changed.
- [ ] PR description clearly explains the change and its impact.

---

## Release notes

- Keep a short **CHANGELOG** in your PR description if user-visible behavior changes (flags, defaults, outputs, filenames, or minimum Python version).

---

## Authors

- Developed by **Mariam Abuelfotouh**, 2026
- Copyright ownership: **Arboretica**
