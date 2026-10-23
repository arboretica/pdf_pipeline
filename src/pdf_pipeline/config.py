"""
Central configuration for pdf_pipeline.

Every tunable (model names, chunk sizes, API-key environment variable names)
lives here. CLI flags override these values; the defaults below are what the
flags fall back to.
"""

# ---------------------------------------------------------------------------
# API key environment variables
# ---------------------------------------------------------------------------

GOOGLE_API_KEY_ENV = "GOOGLE_API_KEY"
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

GEMINI_MODEL = "gemini-2.0-flash"
EMBEDDING_MODEL = "text-embedding-3-small"

# ---------------------------------------------------------------------------
# Chunking (Step 3)
# ---------------------------------------------------------------------------

MAX_CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200
