# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-10-23

### Added

- Three-step pipeline CLI: `pdf-pipeline convert` (PDF → markdown via marker-pdf
  + Gemini figure transcription), `pdf-pipeline extract-toc` (existing-TOC
  detection with heading-hierarchy fallback), and `pdf-pipeline chunk-embed`
  (TOC-guided chunking, table separation, OpenAI embeddings, one FAISS store
  per report).
- `chunk-embed --dry` — keyless chunk preview (no OpenAI key required).
- `pdf-pipeline smoke-test` — keyless end-to-end check on bundled sample data,
  with an optional `--with-convert` step that also runs marker-pdf.
- Bundled sample data shipped inside the package: a 1-page synthetic PDF and a
  marker-style markdown fixture.
- Central `config.py` holding every tunable (model names, chunk sizes, API-key
  env-var names); CLI flag defaults are sourced from it.
- `-v` / `-vv` verbosity flags for INFO/DEBUG logging.
- API-key resolution precedence: CLI flags → environment variables → `.env`
  file; keys are never logged.

[Unreleased]: https://github.com/arboretica/pdf_pipeline/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/arboretica/pdf_pipeline/releases/tag/v0.1.0
