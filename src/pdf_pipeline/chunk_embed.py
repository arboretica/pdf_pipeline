"""
Step 3: Chunk & Embed Markdown Files into FAISS Vector Stores.

Reads each _updated.md report, splits into subsection-level chunks guided
by a TOC JSON, separates tables and figures into dedicated chunks, applies
recursive splitting for oversized text chunks, embeds with OpenAI, and
persists one FAISS vector store per report.
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from pdf_pipeline import config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Text normalisation
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    """Normalise a heading string for fuzzy comparison."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)       # remove bold
    text = re.sub(r"<[^>]+>", "", text)                  # remove HTML tags
    text = re.sub(r"[^\w\s]", "", text.lower()).strip()   # remove punctuation
    return text


# ---------------------------------------------------------------------------
# TOC loading & hierarchy inference
# ---------------------------------------------------------------------------

def load_toc_json(toc_json_path: str | Path) -> dict:
    """Load the structured ToC JSON file."""
    with open(toc_json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _infer_depth_from_title(title: str) -> int:
    """
    Infer nesting depth from numbering in the title.
    '1' → 1, '1.2' → 2, '1.2.3' → 3, 'Summary' → 0 (top-level unnumbered).
    """
    stripped = re.sub(r"<[^>]+>", "", title).strip()

    # Match dotted numbering: 1.2.3
    m = re.match(r"^(\d+(?:\.\d+)*)\b", stripped)
    if m:
        return m.group(1).count(".") + 1

    # Match 'Chapter N' style
    m = re.match(r"^Chapter\s+\d+", stripped, re.IGNORECASE)
    if m:
        return 1

    # Match Roman numerals at start (I., II., XIV.)
    m = re.match(r"^(X{0,3})(IX|IV|V?I{0,3})[\.\s]", stripped)
    if m and (m.group(1) or m.group(2)):
        return 2

    return 0


def build_hierarchy(headings: list[dict], report_has_levels: bool) -> list[dict]:
    """
    Augment each heading with a ``parent_sections`` breadcrumb list.

    If the report's TOC has meaningful level data, use it.
    Otherwise, infer depth from title numbering.
    """
    enriched: list[dict] = []
    parent_stack: list[tuple[int, str]] = []

    for h in headings:
        title = h["title"]

        if report_has_levels and h.get("level", 1) != 1:
            depth = h["level"]
        else:
            depth = _infer_depth_from_title(title)

        while parent_stack and parent_stack[-1][0] >= depth:
            parent_stack.pop()

        parent_sections = [t for _, t in parent_stack]

        enriched.append({
            **h,
            "depth": depth,
            "parent_sections": list(parent_sections),
        })

        parent_stack.append((depth, title))

    return enriched


# ---------------------------------------------------------------------------
# Section extraction from markdown
# ---------------------------------------------------------------------------

def extract_sections(md_content: str, headings: list[dict]) -> list[dict]:
    """
    Split markdown content into sections guided by the TOC headings.

    Returns a list of dicts:
        {title, depth, parent_sections, content, heading_line_idx}
    """
    lines = md_content.split("\n")
    heading_re = re.compile(r"^(#{1,6})\s+(.+)$")

    toc_norm = [_normalise(h["title"]) for h in headings]

    matched_positions: list[tuple[int, int]] = []
    used_toc_indices: set[int] = set()

    for line_idx, line in enumerate(lines):
        m = heading_re.match(line.strip())
        if not m:
            continue
        line_norm = _normalise(m.group(2))

        for toc_idx, tn in enumerate(toc_norm):
            if toc_idx in used_toc_indices:
                continue
            if tn in line_norm or line_norm in tn:
                matched_positions.append((line_idx, toc_idx))
                used_toc_indices.add(toc_idx)
                break

    matched_positions.sort(key=lambda x: x[0])

    sections: list[dict] = []

    # Content before first matched heading → Preamble
    if matched_positions:
        first_line = matched_positions[0][0]
        if first_line > 0:
            preamble = "\n".join(lines[:first_line]).strip()
            if preamble:
                sections.append({
                    "title": "Preamble",
                    "depth": 0,
                    "parent_sections": [],
                    "content": preamble,
                    "heading_line_idx": 0,
                })

    for i, (line_idx, toc_idx) in enumerate(matched_positions):
        h = headings[toc_idx]
        end_line = matched_positions[i + 1][0] if i + 1 < len(matched_positions) else len(lines)
        content = "\n".join(lines[line_idx:end_line]).strip()

        sections.append({
            "title": h["title"],
            "depth": h["depth"],
            "parent_sections": h["parent_sections"],
            "content": content,
            "heading_line_idx": line_idx,
        })

    return sections


# ---------------------------------------------------------------------------
# Table separation
# ---------------------------------------------------------------------------

_TABLE_LINE_RE = re.compile(r"^\s*\|")
_GEMINI_COMMENT_RE = re.compile(r"<!--\s*GEMINI\s+TRANSCRIPTION.*?-->", re.IGNORECASE)


def _is_table_line(line: str) -> bool:
    return bool(_TABLE_LINE_RE.match(line))


def separate_tables(
    content: str,
    section_title: str,
    parent_sections: list[str],
    depth: int,
) -> list[dict]:
    """
    Split a section's content into text and table parts.
    Figure/image lines are kept inline with text.

    Returns list of dicts with keys: text, chunk_type, section_title,
    parent_sections, depth.
    """
    lines = content.split("\n")
    parts: list[dict] = []

    text_buf: list[str] = []
    table_buf: list[str] = []
    in_table = False

    def flush_text():
        nonlocal text_buf
        t = "\n".join(text_buf).strip()
        if t:
            parts.append({
                "text": t,
                "chunk_type": "text",
                "section_title": section_title,
                "parent_sections": parent_sections,
                "depth": depth,
            })
        text_buf = []

    def flush_table():
        nonlocal table_buf, in_table
        t = "\n".join(table_buf).strip()
        if t:
            parts.append({
                "text": t,
                "chunk_type": "table",
                "section_title": section_title,
                "parent_sections": parent_sections,
                "depth": depth,
            })
        table_buf = []
        in_table = False

    for line in lines:
        # Skip Gemini transcription comments
        if _GEMINI_COMMENT_RE.search(line):
            continue

        is_tbl = _is_table_line(line)

        if is_tbl:
            if not in_table:
                flush_text()
                in_table = True
            table_buf.append(line)
            continue

        if in_table and not is_tbl:
            flush_table()

        text_buf.append(line)

    if in_table:
        flush_table()
    flush_text()

    return parts


# ---------------------------------------------------------------------------
# Recursive chunking
# ---------------------------------------------------------------------------

def _build_breadcrumb(parent_sections: list[str], section_title: str) -> str:
    """Build a hierarchical breadcrumb string."""
    parts = parent_sections + [section_title]
    clean = [re.sub(r"<[^>]+>", "", p).strip() for p in parts if p]
    return " > ".join(clean)


def chunk_section_parts(
    parts: list[dict],
    report_name: str,
    source_file: str,
    max_chunk_size: int = config.MAX_CHUNK_SIZE,
    chunk_overlap: int = config.CHUNK_OVERLAP,
) -> list[Document]:
    """
    Take the separated parts (text/table/figure) for a section and
    produce final LangChain Documents, recursively splitting oversized
    text chunks.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        keep_separator=True,
    )

    documents: list[Document] = []
    chunk_idx = 0

    for part in parts:
        text = part["text"]
        chunk_type = part["chunk_type"]
        section_title = part["section_title"]
        parent_sections = part["parent_sections"]
        breadcrumb = _build_breadcrumb(parent_sections, section_title)

        base_metadata = {
            "report_name": report_name,
            "section_title": section_title,
            "parent_sections": parent_sections,
            "breadcrumb": breadcrumb,
            "chunk_type": chunk_type,
            "source_file": source_file,
        }

        if chunk_type in ("table", "figure"):
            page_content = f"[{breadcrumb}]\n\n{text}" if breadcrumb else text
            documents.append(Document(
                page_content=page_content,
                metadata={**base_metadata, "chunk_index": chunk_idx},
            ))
            chunk_idx += 1
        else:
            if len(text) <= max_chunk_size:
                page_content = f"[{breadcrumb}]\n\n{text}" if breadcrumb else text
                documents.append(Document(
                    page_content=page_content,
                    metadata={**base_metadata, "chunk_index": chunk_idx},
                ))
                chunk_idx += 1
            else:
                sub_chunks = splitter.split_text(text)
                for sub in sub_chunks:
                    page_content = f"[{breadcrumb}]\n\n{sub}" if breadcrumb else sub
                    documents.append(Document(
                        page_content=page_content,
                        metadata={**base_metadata, "chunk_index": chunk_idx},
                    ))
                    chunk_idx += 1

    return documents


# ---------------------------------------------------------------------------
# Per-report orchestration
# ---------------------------------------------------------------------------

def build_chunks_for_report(
    report_name: str,
    report_info: dict,
    headings_enriched: list[dict],
    markdown_dir: str | Path,
    max_chunk_size: int = config.MAX_CHUNK_SIZE,
    chunk_overlap: int = config.CHUNK_OVERLAP,
) -> list[Document]:
    """Build all Document chunks for a single report."""
    source_file = report_info["source_file"]
    md_path = Path(source_file)

    if not md_path.exists():
        report_dir = Path(markdown_dir) / report_name
        updated_files = list(report_dir.glob("*_updated.md"))
        if not updated_files:
            print(f"  [SKIP] No _updated.md found for {report_name}")
            return []
        md_path = updated_files[0]

    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    sections = extract_sections(md_content, headings_enriched)

    all_docs: list[Document] = []

    for section in sections:
        parts = separate_tables(
            section["content"],
            section["title"],
            section["parent_sections"],
            section["depth"],
        )

        docs = chunk_section_parts(
            parts,
            report_name=report_name,
            source_file=str(md_path),
            max_chunk_size=max_chunk_size,
            chunk_overlap=chunk_overlap,
        )
        all_docs.extend(docs)

    return all_docs


# ---------------------------------------------------------------------------
# Embedding & FAISS persistence
# ---------------------------------------------------------------------------

def embed_and_save(
    report_name: str,
    documents: list[Document],
    faiss_store_dir: str | Path,
    embeddings: OpenAIEmbeddings,
) -> Optional[FAISS]:
    """Embed documents and save FAISS vector store for a single report."""
    if not documents:
        print(f"  [SKIP] No documents to embed for {report_name}")
        return None

    store_dir = Path(faiss_store_dir) / report_name
    store_dir.mkdir(parents=True, exist_ok=True)

    print(f"  Embedding {len(documents)} chunks...")
    vectorstore = FAISS.from_documents(documents, embeddings)
    vectorstore.save_local(str(store_dir))
    print(f"  Saved FAISS store -> {store_dir}")

    return vectorstore


def load_vectorstore(
    report_name: str,
    faiss_store_dir: str | Path,
    embeddings: OpenAIEmbeddings,
) -> FAISS:
    """Load a previously saved FAISS vector store for a report."""
    store_dir = Path(faiss_store_dir) / report_name
    if not store_dir.exists():
        raise FileNotFoundError(f"No FAISS store found at {store_dir}")
    return FAISS.load_local(
        str(store_dir), embeddings, allow_dangerous_deserialization=True,
    )


# ---------------------------------------------------------------------------
# Main pipeline entry point
# ---------------------------------------------------------------------------

def run_chunk_embed(
    markdown_dir: str,
    toc_json_path: str,
    output_dir: str,
    openai_api_key: str | None,
    embedding_model: str = config.EMBEDDING_MODEL,
    max_chunk_size: int = config.MAX_CHUNK_SIZE,
    chunk_overlap: int = config.CHUNK_OVERLAP,
    skip_reports: list[str] | None = None,
    dry_run: bool = False,
) -> None:
    """
    Full pipeline: load TOC, chunk every report, embed, and save FAISS stores.

    With ``dry_run=True`` no embeddings are created and nothing is saved —
    an OpenAI API key is not required.
    """
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

    embeddings: OpenAIEmbeddings | None = None
    if not dry_run:
        if not openai_api_key:
            raise ValueError(
                "OpenAI API key required for embedding. Pass --openai-api-key or "
                "set OPENAI_API_KEY. (Use --dry to preview chunks without a key.)"
            )
        os.environ["OPENAI_API_KEY"] = openai_api_key
        embeddings = OpenAIEmbeddings(model=embedding_model)
        logger.debug("Initialised OpenAIEmbeddings(model=%s)", embedding_model)

    faiss_store_dir = Path(output_dir)
    if not dry_run:
        faiss_store_dir.mkdir(parents=True, exist_ok=True)

    toc_data = load_toc_json(toc_json_path)
    skip_set = set(skip_reports or [])

    total_chunks = 0
    total_text = 0
    total_table = 0

    for report_name, report_info in toc_data.items():
        if report_name in skip_set:
            print(f"\n[SKIP] {report_name} (in skip list)")
            continue

        print(f"\n{'=' * 60}")
        print(f"Processing: {report_name}")
        print(f"{'=' * 60}")

        headings = report_info.get("headings", [])
        has_levels = any(h.get("level", 1) != 1 for h in headings)

        enriched = build_hierarchy(headings, has_levels)

        documents = build_chunks_for_report(
            report_name, report_info, enriched,
            markdown_dir=markdown_dir,
            max_chunk_size=max_chunk_size,
            chunk_overlap=chunk_overlap,
        )
        logger.debug(
            "Built %d chunks for %s (max_chunk_size=%d, chunk_overlap=%d)",
            len(documents), report_name, max_chunk_size, chunk_overlap,
        )

        n_text = sum(1 for d in documents if d.metadata["chunk_type"] == "text")
        n_table = sum(1 for d in documents if d.metadata["chunk_type"] == "table")
        print(f"  Chunks: {len(documents)} total (text: {n_text}, table: {n_table})")

        total_chunks += len(documents)
        total_text += n_text
        total_table += n_table

        if documents:
            sample = documents[0]
            print(f"\n  --- Sample chunk (index 0) ---")
            print(f"  Metadata: {json.dumps(sample.metadata, indent=4, default=str)}")
            preview = sample.page_content[:300]
            print(f"  Content:  {preview}...")
            logger.debug("Sample chunk full content:\n%s", sample.page_content)

        if not dry_run:
            embed_and_save(report_name, documents, faiss_store_dir, embeddings)

    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Reports processed : {len(toc_data) - len(skip_set)}")
    print(f"  Total chunks      : {total_chunks}")
    print(f"  Text chunks       : {total_text}")
    print(f"  Table chunks      : {total_table}")

    if not dry_run:
        print(f"  Stores saved to   : {faiss_store_dir}")
        print(f"\n  Verifying stores load correctly...")
        for report_name in toc_data:
            if report_name in skip_set:
                continue
            try:
                vs = load_vectorstore(report_name, faiss_store_dir, embeddings)
                n = len(vs.index_to_docstore_id)
                print(f"    OK {report_name}: {n} vectors")
            except Exception as e:
                print(f"    FAIL {report_name}: {e}")
