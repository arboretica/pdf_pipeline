# Security Policy

Thanks for helping keep this project and its users safe. This document explains how to report a vulnerability and what we do to mitigate risk.

## Supported Versions

Until v1.0, we provide security fixes for the **`main`** branch only.

## Reporting a Vulnerability

- **Do not open a public issue.**
- Use **GitHub Security Advisories** to privately report vulnerabilities: https://docs.github.com/en/code-security/security-advisories/repository-security-advisories/creating-a-repository-security-advisory
- If Security Advisories are not available, contact the maintainer via the repository owner's GitHub profile and include:
  - A description of the issue and potential impact
  - Steps to reproduce (PoC), logs, and environment details
  - A suggested severity (CVSS if you have it)

We aim to acknowledge within **72 hours** and provide an initial assessment within **7 days**.

## Scope & Environment

This repository is a document-processing pipeline that:

- Reads PDF files from a local directory and converts them to markdown (marker-pdf, with optional Google Gemini figure transcription)
- Extracts tables of contents from markdown documents
- Sends text chunks to the OpenAI embeddings API and writes one FAISS vector store per report to local disk

**Out of scope:** Attacks that require privileged local access, issues in third-party services/libraries (report those upstream), or malicious input files supplied by the person running the pipeline themselves.

## Handling Secrets

- Never commit API keys or tokens. Prefer environment variables or a local `.env` file ignored by Git.
- Rotate credentials that may have been exposed (e.g., in logs or crash reports).
- Mask keys in debug output. If a secret appears in logs, treat it as compromised.
- Pipeline commands accept `--google-api-key` / `--openai-api-key` flags; prefer environment variables when scripting to keep secrets out of shell history.

## Dependency Security

We rely on third-party libraries. To reduce supply-chain risk:

- Keep dependencies updated (consider Dependabot or similar).
- Dependencies are declared with pinned minimum versions and major-version caps in `pyproject.toml`.
- Avoid adding packages that execute code at import time without review.

## Vulnerability Disclosure & Patch Process

1. Triage and reproduce.
2. Assess impact and draft a minimal fix.
3. Land the fix on `main` and cut a patch release if versioned.
4. Credit the reporter (optional, with permission).
5. Publish a short advisory noting affected versions, mitigation, and fixes.

## Hardening Recommendations (for users)

- Run in an isolated virtual environment (venv/conda).
- Do not run the pipeline with elevated privileges.
- Only process PDFs from sources you trust; documents are parsed by external tools and their content is sent to third-party APIs.
- Review generated markdown and vector stores before further distribution.
