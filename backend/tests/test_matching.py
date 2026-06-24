"""Face matching threshold correctness (SQLite path).

The PostgreSQL HNSW KNN path is exercised by CI's `alembic upgrade head` on a
real pgvector service; this covers the cosine/threshold selection logic that
both paths share.
"""
from app.database import SessionLocal
from app.models import models
from app.services import matching
from tests.conftest import make_user


def _vec(*xs):
    v = list(xs) + [0.0] * (512 - len(xs))
    return v[:512]


def _seed_event_with_faces(faces):
    """faces: list of embedding vectors. Returns (event_id, [photo_ids])."""
    owner = make_user(role="user", email="m@test.ai", firebase_uid="m-uid")
    db = SessionLocal()
    ids = []
    try:
        e = models.Event(title="E", event_slug="m-1", photographer_id=owner.id)
        db.add(e); db.commit(); db.refresh(e)
        for emb in faces:
            p = models.Photo(event_id=e.id, filename="x.jpg", filepath="x.jpg")
            db.add(p); db.commit(); db.refresh(p)
            db.add(models.FaceEmbedding(photo_id=p.id, event_id=e.id, embedding=emb))
            db.commit()
            ids.append(p.id)
        return e.id, ids
    finally:
        db.close()


def test_match_returns_only_above_threshold():
    near = _vec(1.0)                 # identical direction to query -> cosine 1.0
    far = _vec(0.0, 1.0)            # orthogonal -> cosine 0.0
    eid, (pid_near, pid_far) = _seed_event_with_faces([near, far])

    db = SessionLocal()
    try:
        matched = matching.match_event(db, eid, _vec(1.0), threshold=0.6)
    finally:
        db.close()

    assert pid_near in matched
    assert pid_far not in matched


def test_match_is_event_scoped():
    eid_a, (pid_a,) = _seed_event_with_faces([_vec(1.0)])
    # A second event with an identical face must not leak into event A's matches.
    owner = make_user(role="user", email="m2@test.ai", firebase_uid="m2-uid")
    db = SessionLocal()
    try:
        e2 = models.Event(title="E2", event_slug="m-2", photographer_id=owner.id)
        db.add(e2); db.commit(); db.refresh(e2)
        p2 = models.Photo(event_id=e2.id, filename="y.jpg", filepath="y.jpg")
        db.add(p2); db.commit(); db.refresh(p2)
        db.add(models.FaceEmbedding(photo_id=p2.id, event_id=e2.id, embedding=_vec(1.0)))
        db.commit()
        matched = matching.match_event(db, eid_a, _vec(1.0), threshold=0.6)
    finally:
        db.close()

    assert matched == {pid_a}
