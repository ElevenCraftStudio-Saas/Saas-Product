"""Event-scoped face matching.

PostgreSQL: pgvector cosine search (fast, indexed) over `embedding_vec`,
plus a Python fallback for any legacy rows whose vector wasn't backfilled.
SQLite (dev/tests): pure-Python cosine over the JSON `embedding` column.
"""
import logging
import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models import models

logger = logging.getLogger("wedfind.matching")


def _cosine(a, b) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1.0
    return float(np.dot(a, b) / denom)


def _to_vec_literal(embedding) -> str:
    return "[" + ",".join(f"{float(x):.8f}" for x in embedding) + "]"


def match_event(db: Session, event_id: int, query_embedding, threshold: float) -> set[int]:
    """Return photo_ids in this event whose face matches the query embedding."""
    matched: set[int] = set()

    if db.bind.dialect.name == "postgresql":
        vec = _to_vec_literal(query_embedding)
        # HNSW KNN: event-scoped pre-filter + ORDER BY <=> LIMIT uses the index
        # (a bare "WHERE distance >= threshold" cannot). Over-fetch K, then keep
        # only those within the cosine threshold (similarity = 1 - distance).
        db.execute(text("SET LOCAL hnsw.ef_search = 100"))
        rows = db.execute(
            text(
                """
                SELECT fe.photo_id, (fe.embedding_vec <=> CAST(:q AS vector)) AS dist
                FROM face_embeddings fe
                WHERE fe.event_id = :eid AND fe.embedding_vec IS NOT NULL
                ORDER BY fe.embedding_vec <=> CAST(:q AS vector)
                LIMIT 100
                """
            ),
            {"eid": event_id, "q": vec},
        ).fetchall()
        for photo_id, dist in rows:
            if (1 - float(dist)) >= threshold:
                matched.add(photo_id)

        # Legacy rows lacking a backfilled vector → compare in Python.
        legacy = db.execute(
            text(
                """
                SELECT fe.photo_id, fe.embedding
                FROM face_embeddings fe
                JOIN photos p ON p.id = fe.photo_id
                WHERE p.event_id = :eid AND fe.embedding_vec IS NULL
                """
            ),
            {"eid": event_id},
        ).fetchall()
        for photo_id, emb in legacy:
            if emb and _cosine(query_embedding, emb) >= threshold:
                matched.add(photo_id)
        return matched

    # SQLite / others: ORM + Python cosine.
    photo_ids = [p.id for p in db.query(models.Photo.id).filter(models.Photo.event_id == event_id).all()]
    if not photo_ids:
        return matched
    for fe in db.query(models.FaceEmbedding).filter(models.FaceEmbedding.photo_id.in_(photo_ids)).all():
        if fe.embedding and _cosine(query_embedding, fe.embedding) >= threshold:
            matched.add(fe.photo_id)
    return matched
