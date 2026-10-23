"""CLI tests using click's CliRunner — keyless, no network, no API keys."""

from click.testing import CliRunner

from pdf_pipeline.cli import main


def _run_smoke_test(tmp_path):
    """Run the bundled smoke test into *tmp_path*; return the result."""
    runner = CliRunner()
    workdir = tmp_path / "out"
    result = runner.invoke(main, ["smoke-test", "--workdir", str(workdir)])
    assert result.exit_code == 0, result.output
    return result, workdir


def test_help_lists_all_commands():
    result = CliRunner().invoke(main, ["--help"])
    assert result.exit_code == 0
    for cmd in ("convert", "extract-toc", "chunk-embed", "smoke-test"):
        assert cmd in result.output


def test_verbose_flags_parse():
    for flags in (["-v", "--help"], ["-vv", "--help"], ["--verbose", "--help"]):
        result = CliRunner().invoke(main, flags)
        assert result.exit_code == 0


def test_smoke_test_runs_keylessly(tmp_path):
    result, workdir = _run_smoke_test(tmp_path)
    assert "SMOKE TEST PASSED" in result.output
    assert (workdir / "toc.json").exists()


def test_chunk_embed_dry_needs_no_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _, workdir = _run_smoke_test(tmp_path)

    result = CliRunner().invoke(main, [
        "chunk-embed", "--dry",
        "--markdown-dir", str(workdir / "markdown_output"),
        "--toc-json", str(workdir / "toc.json"),
        "--output-dir", str(workdir / "faiss_stores"),
    ])
    assert result.exit_code == 0, result.output
    assert "SUMMARY" in result.output


def test_chunk_embed_requires_key_without_dry(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _, workdir = _run_smoke_test(tmp_path)

    result = CliRunner().invoke(main, [
        "chunk-embed",
        "--markdown-dir", str(workdir / "markdown_output"),
        "--toc-json", str(workdir / "toc.json"),
        "--output-dir", str(workdir / "faiss_stores"),
    ])
    assert result.exit_code != 0
    assert "OpenAI API key required" in result.output
