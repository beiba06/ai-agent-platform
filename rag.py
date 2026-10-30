"""Document search: SQLite full-text search (BM25), one in-memory index per chat."""
import io
import re
import sqlite3
import textwrap

from pypdf import PdfReader

MAX_PASSAGES = 500  # keeps memory bounded: at most ~400 KB of text per chat
indexes: dict[str, sqlite3.Connection] = {}  # session id -> that chat's index


def read(name: str, data: bytes) -> list[tuple[str, str]]:
    """Split a PDF or text file into (label, passage) pairs; labels name the file and page."""
    if name.lower().endswith(".pdf"):
        pages = ((f"{name} p.{i}", page.extract_text() or "") for i, page in enumerate(PdfReader(io.BytesIO(data)).pages, 1))
    else:
        pages = [(name, data.decode("utf-8", errors="replace"))]
    passages = []
    for label, text in pages:
        passages += [(label, passage) for passage in textwrap.wrap(text, 800)]
        if len(passages) > MAX_PASSAGES:  # one extra tells the caller the file was cut short
            break
    return passages


def add(session_id: str, passages: list[tuple[str, str]]) -> None:
    """Replace this chat's index: each chat holds one file."""
    forget(session_id)
    db = indexes[session_id] = sqlite3.connect(":memory:", check_same_thread=False)
    db.execute("CREATE VIRTUAL TABLE passages USING fts5(label UNINDEXED, text, tokenize='porter')")
    db.executemany("INSERT INTO passages VALUES (?, ?)", passages)


def forget(session_id: str) -> None:
    if db := indexes.pop(session_id, None):
        db.close()


def search(session_id: str, query: str, limit: int = 5) -> list[tuple[str, str]]:
    """Return the best (label, passage) pairs by BM25, or the opening passages if no word matches."""
    db = indexes.get(session_id)
    if not db:
        return []
    words = " OR ".join(f'"{word}"' for word in re.findall(r"\w+", query))  # quoted, so FTS5 syntax can't be injected
    rows = db.execute("SELECT label, text FROM passages WHERE passages MATCH ? ORDER BY rank LIMIT ?", (words, limit)).fetchall() if words else []
    return rows or db.execute("SELECT label, text FROM passages LIMIT ?", (limit,)).fetchall()
