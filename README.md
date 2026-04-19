# pdf_pipeline

A three-step Python pipeline that converts PDF reports into searchable vector stores.

1. **Convert** — turns PDFs into clean markdown using [marker-pdf](https://github.com/VikParuchuri/marker), then enhances figure-heavy pages with Google Gemini vision.
2. **Extract TOC** — detects or builds a structured table of contents from each markdown report.
3. **Chunk & Embed** — splits markdown into semantically meaningful chunks guided by the TOC, embeds them with OpenAI, and saves per-report [FAISS](https://github.com/facebookresearch/faiss) vector stores.

---

## Quick Start

```bash
# 1. Clone & install
git clone https://github.com/<your-org>/pdf_pipeline.git
cd pdf_pipeline
pip install -e .

# 2. Supply API keys (pick one method)
#    a) CLI flags   --google-api-key / --openai-api-key
#    b) Env vars    export GOOGLE_API_KEY=... && export OPENAI_API_KEY=...
#    c) .env file   cp .env.example .env  (then edit)

# 3. Run the pipeline
pdf-pipeline convert     --pdf-dir ./pdfs --output-dir ./md_output --google-api-key <KEY>
pdf-pipeline extract-toc --markdown-dir ./md_output --output-json ./toc.json
pdf-pipeline chunk-embed --markdown-dir ./md_output --toc-json ./toc.json --output-dir ./faiss_stores --openai-api-key <KEY>
```

---

## Requirements

- **Python 3.10+**
- API keys for **Google Gemini** (Step 1) and **OpenAI** (Step 3)
- `poppler-utils` if you use the optional `pdf2image` dependency  
  (`brew install poppler` on macOS, `apt install poppler-utils` on Debian/Ubuntu)

## Installation

```bash
pip install -e .
```

All Python dependencies are declared in `pyproject.toml` and installed automatically.

---

## Usage

Every command is a subcommand of `pdf-pipeline`. Run `pdf-pipeline --help` for the full list.

### Step 1 — Convert PDFs to Markdown

```bash
pdf-pipeline convert \
    --pdf-dir ./pdfs \
    --output-dir ./markdown_output \
    --google-api-key YOUR_KEY
```

| Flag | Description |
|---|---|
| `--pdf-dir` | Directory containing the source PDF files **(required)** |
| `--output-dir` | Where marker-pdf writes its markdown output **(required)** |
| `--google-api-key` | Gemini API key (falls back to `GOOGLE_API_KEY` env var) |
| `--gemini-model` | Gemini model name (default: `gemini-2.0-flash`) |
| `--marker-only` | Only run marker-pdf, skip Gemini enhancement |
| `--enhance-only` | Only run Gemini enhancement (marker output must already exist) |

**What it does:**

1. Runs `marker-pdf` over every PDF in `--pdf-dir`, producing one markdown directory per file.
2. Scans each directory for pages that contain figures (`_page_N_Figure_*.jpeg`).
3. Sends those pages to Gemini as single-page PDFs and inserts the returned markdown before the figure references.

### Step 2 — Extract Table of Contents

```bash
pdf-pipeline extract-toc \
    --markdown-dir ./markdown_output \
    --output-json ./toc.json \
    --output-md ./toc.md        # optional
```

| Flag | Description |
|---|---|
| `--markdown-dir` | Directory containing markdown report sub-directories **(required)** |
| `--output-json` | Path for the structured TOC JSON file **(required)** |
| `--output-md` | Optional path for a human-readable combined TOC markdown file |

**What it does:**

For each report directory it first looks for an existing TOC section in the markdown. If found (≥ 3 entries) it uses that; otherwise it builds a TOC from the document's heading hierarchy. Results are saved as JSON for use by Step 3.

### Step 3 — Chunk & Embed into FAISS

```bash
pdf-pipeline chunk-embed \
    --markdown-dir ./markdown_output \
    --toc-json ./toc.json \
    --output-dir ./faiss_stores \
    --openai-api-key YOUR_KEY
```

| Flag | Description |
|---|---|
| `--markdown-dir` | Directory containing markdown report sub-directories **(required)** |
| `--toc-json` | TOC JSON produced by Step 2 **(required)** |
| `--output-dir` | Where FAISS stores are saved (one sub-directory per report) **(required)** |
| `--openai-api-key` | OpenAI API key (falls back to `OPENAI_API_KEY` env var) |
| `--embedding-model` | OpenAI embedding model (default: `text-embedding-3-small`) |
| `--max-chunk-size` | Max chunk size in characters (default: `1500`) |
| `--chunk-overlap` | Overlap between chunks in characters (default: `200`) |
| `--skip` | Report name to skip (repeatable) |
| `--dry` | Preview chunks without embedding or saving |

**What it does:**

1. Loads the TOC JSON and infers a section hierarchy for each report.
2. Splits each report's markdown into sections, then separates tables from text.
3. Applies recursive character splitting to oversized text chunks.
4. Embeds all chunks with OpenAI and saves one FAISS index per report.

---

## API Key Precedence

For both `--openai-api-key` and `--google-api-key`:

| Priority | Source |
|---|---|
| 1 (highest) | CLI argument |
| 2 | Environment variable (`OPENAI_API_KEY` / `GOOGLE_API_KEY`) |
| 3 | `.env` file (auto-loaded via `python-dotenv`) |

---

## Project Structure

```
pdf_pipeline/
├── pyproject.toml                 # Package metadata & dependencies
├── README.md
├── requirements.txt               # Flat dependency list (convenience)
├── .env.example                   # API key template
├── src/
│   └── pdf_pipeline/
│       ├── __init__.py            # Version
│       ├── cli.py                 # Click CLI (convert, extract-toc, chunk-embed)
│       ├── convert.py             # Step 1 — PDF → Markdown
│       ├── extract_toc.py         # Step 2 — TOC extraction
│       └── chunk_embed.py         # Step 3 — Chunk & embed
├── tests/
│   └── test_extract_toc.py        # Unit tests
└── original/                      # Archived original scripts for reference
```

---

## Development

```bash
# Install in editable mode
pip install -e .

# Run tests
pip install pytest
pytest tests/ -v

# Verify CLI
pdf-pipeline --help
```

## License

MIT
