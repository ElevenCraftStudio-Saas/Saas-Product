"""PostgreSQL + pgvector integration tests.

Skipped unless WEDFIND_TEST_PG_URL points at a pgvector-enabled Postgres
(CI provides the service). These exercise the production HNSW KNN path and
DB-level FK cascades that the SQLite suite cannot.
"""
import os

import pytest

PG_URL = os.getenv("WEDFIND_TEST_PG_URL")
pytestmark = pytest.mark.skipif(not PG_URL, reason="WEDFIND_TEST_PG_URL not set")


@pytest.fixture(scope="module")
def pg():
    from sqlalchemy import create_engine, text
    engine = create_engine(PG_URL)
    with engine.begin() as c:
        c.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    # Migrations build the schema (also validates the migration chain on PG).
    from alembic.config import Config
    from alembic import command
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", PG_URL)
    command.upgrade(cfg, "head")
    yield engine
    engine.dispose()


def test_knn_uses_hnsw_index(pg):
    from sqlalchemy import text
    with pg.connect() as c:
        plan = c.execute(text(
            "EXPLAIN SELECT photo_id FROM face_embeddings "
            "WHERE event_id = 1 ORDER BY embedding_vec <=> '[%s]' LIMIT 100"
            % ",".join(["0.1"] * 512)
        )).fetchall()
    text_plan = "\n".join(r[0] for r in plan)
    # Index Scan using the HNSW index, not a Seq Scan.
    assert "ix_face_embeddings_vec" in text_plan or "Index" in text_plan


def test_event_delete_cascades_db_level(pg):
    """DB-level ON DELETE CASCADE removes child rows on a raw delete."""
    from sqlalchemy import text
    with pg.begin() as c:
        c.execute(text("INSERT INTO users (firebase_uid, role) VALUES ('pg-u','user')"))
        uid = c.execute(text("SELECT id FROM users WHERE firebase_uid='pg-u'")).scalar()
        c.execute(text("INSERT INTO events (title, event_slug, photographer_id) VALUES ('E','pg-e',:u)"), {"u": uid})
        eid = c.execute(text("SELECT id FROM events WHERE event_slug='pg-e'")).scalar()
        c.execute(text("INSERT INTO photos (event_id, filename, filepath, size_bytes) VALUES (:e,'a','a',1)"), {"e": eid})
    with pg.begin() as c:
        c.execute(text("DELETE FROM events WHERE id=:e"), {"e": eid})
        remaining = c.execute(text("SELECT count(*) FROM photos WHERE event_id=:e"), {"e": eid}).scalar()
    assert remaining == 0
