"""
Step 2: Extract Table of Contents from Markdown Files.

Searches for an existing TOC section in each document; falls back to
building a TOC from markdown headings.
"""

import json
import re
from pathlib import Path


# ---------------------------------------------------------------------------
# TOC detection in existing documents
# ---------------------------------------------------------------------------

def find_existing_toc(content: str) -> tuple[bool, str | None, list[dict]]:
    """Search for an existing Table of Contents section in the markdown content.

    Returns:
        (found, toc_content, toc_entries)
    """
    lines = content.split("\n")
    toc_start = None
    toc_end = None

    # Patterns to identify TOC heading
    toc_heading_patterns = [
        r"^#+\s*\**Table\s+of\s+Contents\**\s*$",
        r"^#+\s*\**Contents\**\s*$",
        r"^#+\s*\**TOC\**\s*$",
        r"^\**Table\s+of\s+Contents\**\s*$",
    ]

    for i, line in enumerate(lines):
        stripped = line.strip()
        for pattern in toc_heading_patterns:
            if re.match(pattern, stripped, re.IGNORECASE):
                toc_start = i
                break
        if toc_start is not None:
            break

    if toc_start is None:
        return False, None, []

    # Find the end of TOC section
    toc_entries: list[dict] = []
    in_table = False

    for i in range(toc_start + 1, len(lines)):
        line = lines[i].strip()

        # Skip empty lines at the start
        if not line and not toc_entries:
            continue

        # Check if we hit a new major section (heading that's not part of TOC)
        if re.match(r"^#{1,2}\s+(?!.*\d+\s*$)", line) and len(toc_entries) > 3:
            toc_end = i
            break

        # Check for markdown table format (common in TOCs)
        if "|" in line:
            in_table = True
            # Extract entry from table row
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if cells and not all(c.replace("-", "") == "" for c in cells):
                entry = cells[0] if cells else ""
                if entry and not entry.startswith("--"):
                    toc_entries.append({"title": entry, "level": 1, "line": i})

        # Check for list-style TOC
        elif re.match(r"^[-*]\s+", line) or re.match(r"^\d+\.\s+", line):
            entry = re.sub(r"^[-*\d.]+\s+", "", line)
            toc_entries.append({"title": entry, "level": 1, "line": i})

        # Check for plain text entries with page numbers
        elif re.match(r"^.+\s+\d+\s*$", line) and len(line) > 5:
            entry = re.sub(r"\s+\d+\s*$", "", line)
            toc_entries.append({"title": entry, "level": 1, "line": i})

        # Stop if we've collected entries and hit empty lines followed by content
        elif not line and len(toc_entries) > 3:
            lookahead = i + 1
            while lookahead < len(lines) and not lines[lookahead].strip():
                lookahead += 1
            if lookahead < len(lines):
                next_line = lines[lookahead].strip()
                if re.match(r"^#{1,3}\s+", next_line) or (
                    len(next_line) > 50 and "|" not in next_line
                ):
                    toc_end = i
                    break

    if toc_end is None:
        toc_end = min(toc_start + 100, len(lines))

    toc_content = "\n".join(lines[toc_start:toc_end])

    return len(toc_entries) > 0, toc_content, toc_entries


# ---------------------------------------------------------------------------
# Heading extraction
# ---------------------------------------------------------------------------

def extract_headings_from_markdown(markdown_path: str | Path) -> list[dict]:
    """Extract all headings from a markdown file."""
    headings: list[dict] = []

    with open(markdown_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")

    for line_num, line in enumerate(lines, 1):
        match = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
        if match:
            level = len(match.group(1))
            title = match.group(2)
            # Clean up the title
            title = re.sub(r"\*\*(.+?)\*\*", r"\1", title)  # Remove bold
            title = re.sub(r"<span[^>]*>", "", title)
            title = re.sub(r"</span>", "", title)
            title = title.strip()

            if title and not title.startswith("![]"):
                headings.append({"level": level, "title": title, "line": line_num})

    return headings


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_toc(headings: list[dict], report_name: str) -> str:
    """Format headings into a readable TOC structure."""
    toc_lines = [f"# Table of Contents: {report_name}\n"]
    for heading in headings:
        indent = "  " * (heading["level"] - 1)
        toc_lines.append(f"{indent}- {heading['title']}")
    return "\n".join(toc_lines)


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------

def process_all_reports(base_dir: str) -> dict:
    """Process all report directories under *base_dir* and extract TOCs."""
    results: dict = {}

    for report_dir in sorted(Path(base_dir).iterdir()):
        if not report_dir.is_dir():
            continue

        report_name = report_dir.name
        md_file = report_dir / f"{report_name}.md"
        updated_md_file = report_dir / f"{report_name}_updated.md"

        target_file = None
        if updated_md_file.exists():
            target_file = updated_md_file
        elif md_file.exists():
            target_file = md_file

        if target_file:
            print(f"Processing: {report_name}")

            with open(target_file, "r", encoding="utf-8") as f:
                content = f.read()

            found_toc, toc_content, toc_entries = find_existing_toc(content)

            if found_toc and len(toc_entries) >= 3:
                print(f"  -> Found existing TOC with {len(toc_entries)} entries")
                results[report_name] = {
                    "file": str(target_file),
                    "source": "existing_toc",
                    "headings": toc_entries,
                    "toc": (
                        f"# Table of Contents: {report_name}\n"
                        "(Extracted from existing TOC in document)\n\n"
                        + "\n".join([f"- {e['title']}" for e in toc_entries])
                    ),
                }
            else:
                print("  -> Building TOC from headings")
                headings = extract_headings_from_markdown(target_file)
                results[report_name] = {
                    "file": str(target_file),
                    "source": "built_from_headings",
                    "headings": headings,
                    "toc": format_toc(headings, report_name),
                }
        else:
            print(f"Warning: No markdown file found for {report_name}")

    return results


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def save_combined_toc(results: dict, output_path: str | Path) -> None:
    """Save all TOCs to a single markdown file."""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Combined Table of Contents - High Level Reports\n\n")
        f.write("This document contains the table of contents extracted from each report.\n\n")
        f.write("---\n\n")
        for _report_name, data in results.items():
            f.write(data["toc"])
            f.write("\n\n---\n\n")
    print(f"\nCombined TOC saved to: {output_path}")


def save_json_toc(results: dict, output_path: str | Path) -> None:
    """Save TOC data as JSON for programmatic access."""
    json_data = {}
    for report_name, data in results.items():
        json_data[report_name] = {
            "source_file": data["file"],
            "toc_source": data.get("source", "unknown"),
            "headings": data["headings"],
        }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)

    print(f"JSON TOC saved to: {output_path}")
