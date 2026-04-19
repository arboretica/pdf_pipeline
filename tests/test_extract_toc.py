"""Basic tests for the extract_toc module (stdlib-only, no external deps)."""

from pdf_pipeline.extract_toc import (
    find_existing_toc,
    extract_headings_from_markdown,
    format_toc,
)
import tempfile
import os


# ---------------------------------------------------------------------------
# find_existing_toc
# ---------------------------------------------------------------------------

def test_find_existing_toc_with_list_style():
    content = """\
# My Report

## Table of Contents

- Introduction
- Methodology
- Results
- Conclusion

## Introduction

Some text here.
"""
    found, toc_content, entries = find_existing_toc(content)
    assert found is True
    assert len(entries) == 4
    assert entries[0]["title"] == "Introduction"
    assert entries[-1]["title"] == "Conclusion"


def test_find_existing_toc_not_present():
    content = """\
# My Report

## Introduction

Some text here.
"""
    found, toc_content, entries = find_existing_toc(content)
    assert found is False
    assert entries == []


def test_find_existing_toc_with_numbered_entries():
    content = """\
# Report

## Contents

1. Overview
2. Background
3. Analysis
4. Summary

## Overview

Text.
"""
    found, toc_content, entries = find_existing_toc(content)
    assert found is True
    assert len(entries) == 4


# ---------------------------------------------------------------------------
# extract_headings_from_markdown
# ---------------------------------------------------------------------------

def test_extract_headings_from_markdown():
    md_content = """\
# Title

## Section One

### Subsection A

## Section Two
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(md_content)
        tmp_path = f.name

    try:
        headings = extract_headings_from_markdown(tmp_path)
        assert len(headings) == 4
        assert headings[0]["level"] == 1
        assert headings[0]["title"] == "Title"
        assert headings[1]["level"] == 2
        assert headings[2]["level"] == 3
        assert headings[2]["title"] == "Subsection A"
    finally:
        os.unlink(tmp_path)


def test_extract_headings_strips_bold():
    md_content = "## **Bold Heading**\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(md_content)
        tmp_path = f.name

    try:
        headings = extract_headings_from_markdown(tmp_path)
        assert len(headings) == 1
        assert headings[0]["title"] == "Bold Heading"
    finally:
        os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# format_toc
# ---------------------------------------------------------------------------

def test_format_toc():
    headings = [
        {"level": 1, "title": "Intro", "line": 1},
        {"level": 2, "title": "Details", "line": 5},
    ]
    result = format_toc(headings, "Test Report")
    assert "# Table of Contents: Test Report" in result
    assert "- Intro" in result
    assert "  - Details" in result


if __name__ == "__main__":
    test_find_existing_toc_with_list_style()
    test_find_existing_toc_not_present()
    test_find_existing_toc_with_numbered_entries()
    test_extract_headings_from_markdown()
    test_extract_headings_strips_bold()
    test_format_toc()
    print("All tests passed!")
