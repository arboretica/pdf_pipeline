"""Tests for the central config module."""

import inspect

from pdf_pipeline import config


def test_defaults_match_documented_values():
    assert config.GEMINI_MODEL == "gemini-2.0-flash"
    assert config.EMBEDDING_MODEL == "text-embedding-3-small"
    assert config.MAX_CHUNK_SIZE == 1500
    assert config.CHUNK_OVERLAP == 200


def test_env_var_names():
    assert config.GOOGLE_API_KEY_ENV == "GOOGLE_API_KEY"
    assert config.OPENAI_API_KEY_ENV == "OPENAI_API_KEY"


def test_chunk_embed_defaults_are_wired_from_config():
    from pdf_pipeline.chunk_embed import run_chunk_embed

    sig = inspect.signature(run_chunk_embed)
    assert sig.parameters["embedding_model"].default == config.EMBEDDING_MODEL
    assert sig.parameters["max_chunk_size"].default == config.MAX_CHUNK_SIZE
    assert sig.parameters["chunk_overlap"].default == config.CHUNK_OVERLAP


def test_convert_defaults_are_wired_from_config():
    from pdf_pipeline.convert import pdf_page_to_markdown_gemini

    sig = inspect.signature(pdf_page_to_markdown_gemini)
    assert sig.parameters["model"].default == config.GEMINI_MODEL
