#!/usr/bin/env python3
"""
FTS5 RAG Client (offline full-text search)

Queries the FTS5 full-text search database — no network or external deps needed.
Same CLI interface as rag-client-local.py but uses BM25 keyword search instead
of vector similarity.

Usage:
    python AgentArchitect/scripts/rag-client-fts.py search "parking rules" --bucket wharfside-docs
    python AgentArchitect/scripts/rag-client-fts.py search "board meeting insurance" --limit 5
    python AgentArchitect/scripts/rag-client-fts.py buckets
    python AgentArchitect/scripts/rag-client-fts.py stats

Requirements: None (Python stdlib only — sqlite3, json, os, sys)
"""

import json
import os
import sqlite3
import sys

# ============================================================================
# Configuration
# ============================================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # abspath, not realpath:
# AgentArchitect/scripts/rag-client-fts.py is a symlink to this file, and must
# resolve to AgentArchitect/data/.
#
# Factory-managed: `aa sync` copies this file into every spawned repo's scripts/.
# Index lookup order:
#   1. $RAG_FTS_DB
#   2. <this repo>/data/rag-fts.db — the full index in AgentArchitect, or a
#      committed single-bucket index in a workspace repo (e.g. wharfside), which
#      is what makes search work in cloud/iOS sessions
#   3. ~/Workspaces/AgentArchitect/data/rag-fts.db — the full index on the Mac
def _find_db():
    candidates = [
        os.environ.get("RAG_FTS_DB"),
        os.path.join(SCRIPT_DIR, "..", "data", "rag-fts.db"),
        os.path.expanduser("~/Workspaces/AgentArchitect/data/rag-fts.db"),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return os.path.normpath(c)
    return os.path.normpath(candidates[1])


DB_PATH = _find_db()

DEFAULT_LIMIT = 10


# ============================================================================
# Helpers
# ============================================================================

def get_connection():
    """Get a SQLite connection to the FTS5 database."""
    if not os.path.exists(DB_PATH):
        print(f"ERROR: FTS5 database not found at {DB_PATH}", file=sys.stderr)
        print("Build it first: python3 ~/Workspaces/AgentArchitect/scripts/build-fts-db.py", file=sys.stderr)
        print("(cloud/iOS: only workspaces with a committed data/rag-fts.db, such as wharfside, have search)", file=sys.stderr)
        sys.exit(1)
    return sqlite3.connect(DB_PATH)


# ============================================================================
# Commands
# ============================================================================

def search(query, bucket=None, limit=DEFAULT_LIMIT):
    """Search the FTS5 database using BM25 ranking."""
    conn = get_connection()

    if bucket:
        sql = """
            SELECT c.bucket_id, c.source_file, c.chunk_index, c.chunk_text, rank
            FROM chunks_fts
            JOIN chunks c ON c.id = chunks_fts.rowid
            WHERE chunks_fts MATCH ? AND c.bucket_id = ?
            ORDER BY rank
            LIMIT ?
        """
        params = (query, bucket, limit)
    else:
        sql = """
            SELECT c.bucket_id, c.source_file, c.chunk_index, c.chunk_text, rank
            FROM chunks_fts
            JOIN chunks c ON c.id = chunks_fts.rowid
            WHERE chunks_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """
        params = (query, limit)

    expanded = False
    try:
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError as e:
        if "fts5: syntax error" in str(e):
            # Retry with quoted query to handle special characters
            escaped = '"' + query.replace('"', '""') + '"'
            if bucket:
                rows = conn.execute(sql, (escaped, bucket, limit)).fetchall()
            else:
                rows = conn.execute(sql, (escaped, limit)).fetchall()
        else:
            raise

    # OR fallback: if AND query returned nothing and query has multiple terms
    if not rows and ' ' in query and 'OR' not in query.upper():
        terms = query.split()
        or_query = ' OR '.join(terms)
        try:
            if bucket:
                rows = conn.execute(sql, (or_query, bucket, limit)).fetchall()
            else:
                rows = conn.execute(sql, (or_query, limit)).fetchall()
            if rows:
                expanded = True
        except sqlite3.OperationalError:
            pass  # If OR query also fails, fall through to no-results

    conn.close()

    if not rows:
        print(f"No results found for: {query}")
        if bucket:
            print(f"  (bucket: {bucket})")
        return

    if expanded:
        print(f"## RAG Search Results: \"{query}\"")
        print(f"**Note:** No exact matches. Showing expanded results (OR matching).")
    else:
        print(f"## RAG Search Results: \"{query}\"")
    if bucket:
        print(f"**Bucket:** {bucket}")
    print(f"**Results:** {len(rows)}")
    print(f"**Search type:** FTS5 (BM25 keyword ranking)\n")

    for i, (bucket_id, source_file, chunk_index, chunk_text, rank) in enumerate(rows, 1):
        print(f"### Result {i} [rank: {rank:.2f}]")
        print(f"**Source:** {source_file}")
        print(f"**Bucket:** {bucket_id}")
        text = chunk_text
        print(f"\n{text[:800]}")
        if len(text) > 800:
            print(f"\n... ({len(text)} chars total)")
        print()


def list_buckets():
    """List available RAG buckets."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT bucket_id, COUNT(*) as doc_count,
               (SELECT COUNT(*) FROM chunks c WHERE c.bucket_id = d.bucket_id) as chunk_count
        FROM documents d
        GROUP BY bucket_id
        ORDER BY bucket_id
    """).fetchall()
    conn.close()

    print("## Available RAG Buckets\n")
    for bucket_id, doc_count, chunk_count in rows:
        print(f"- **{bucket_id}** -- {doc_count} documents, {chunk_count} chunks")


def stats():
    """Get FTS5 database statistics."""
    conn = get_connection()
    docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    tokens = conn.execute("SELECT COALESCE(SUM(total_tokens), 0) FROM documents").fetchone()[0]

    rows = conn.execute("""
        SELECT bucket_id, COUNT(*) FROM documents GROUP BY bucket_id ORDER BY bucket_id
    """).fetchall()
    conn.close()

    by_bucket = {r[0]: r[1] for r in rows}

    print("## RAG Database Statistics\n")
    print(f"**Backend:** FTS5 (offline full-text search)")
    print(f"**Database:** {DB_PATH}")
    print(f"**Documents:** {docs}")
    print(f"**Chunks:** {chunks}")
    print(f"**Tokens:** {tokens}")
    print(f"**Buckets:** {json.dumps(by_bucket, indent=2)}")


# ============================================================================
# CLI
# ============================================================================

def print_usage():
    print("""
FTS5 RAG Client (offline full-text search)

Usage:
  python rag-client-fts.py search <query> [--bucket <id>] [--limit <n>]
  python rag-client-fts.py buckets
  python rag-client-fts.py stats

Examples:
  python rag-client-fts.py search "parking rules" --bucket wharfside-docs
  python rag-client-fts.py search "board meeting minutes" --limit 5
  python rag-client-fts.py search "insurance deductible" --bucket wharfside-docs
  python rag-client-fts.py buckets

Tips:
  - Use specific keywords, not natural language (FTS5 is keyword-based)
  - Multi-word queries match documents containing ALL terms
  - Use OR for alternatives: "parking OR vehicles"
  - Use * for prefix matching: "insur*" matches insurance, insured, etc.
  - Stemming is enabled: "parking" also matches "parked", "parks"
""")


def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    command = sys.argv[1]

    if command == "search":
        if len(sys.argv) < 3:
            print("ERROR: search requires a query string", file=sys.stderr)
            sys.exit(1)

        query = sys.argv[2]
        bucket = None
        limit = DEFAULT_LIMIT

        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == "--bucket" and i + 1 < len(sys.argv):
                bucket = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--limit" and i + 1 < len(sys.argv):
                limit = int(sys.argv[i + 1])
                i += 2
            else:
                query += " " + sys.argv[i]
                i += 1

        search(query, bucket=bucket, limit=limit)

    elif command == "buckets":
        list_buckets()

    elif command == "stats":
        stats()

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
