import json

import psycopg
import pytest

from tape_service.db.score import AlreadyScored, save

pytestmark = pytest.mark.integration


@pytest.fixture
def clean_alpha_role1_doc1(pg_dsn):
    """Delete any prior score for (user=1, role=1, document=1) so tests
    that exercise the happy path start fresh. Synthetic seed only."""
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM score.score "
                "WHERE user_id = 1 AND role_id = 1 AND document_id = 1"
            )
    yield


def test_save_happy_path_returns_int(pg_dsn, clean_alpha_role1_doc1):
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        sid = save(
            conn, user_id=1, document_id=1, role_id=1,
            verdict={"verdict": "yes"}, comment=None,
        )
        assert isinstance(sid, int) and sid > 0


def test_save_duplicate_raises_already_scored(pg_dsn, clean_alpha_role1_doc1):
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        save(conn, user_id=1, document_id=1, role_id=1,
             verdict={"verdict": "yes"}, comment=None)
        with pytest.raises(AlreadyScored):
            save(conn, user_id=1, document_id=1, role_id=1,
                 verdict={"verdict": "no"}, comment="dup")


def test_notify_fires_on_insert(pg_dsn, clean_alpha_role1_doc1):
    """The score._notify_tape_inserted trigger (docs/sql/03) emits a
    pg_notify on the tape_score_inserted channel; the worker LISTENs."""
    with psycopg.connect(pg_dsn, autocommit=True) as listener:
        with listener.cursor() as cur:
            cur.execute("LISTEN tape_score_inserted")

        with psycopg.connect(pg_dsn, autocommit=True) as writer:
            save(writer, user_id=1, document_id=1, role_id=1,
                 verdict={"verdict": "unsure"}, comment=None)

        payload = None
        for note in listener.notifies(timeout=2.0):
            if note.channel == "tape_score_inserted":
                payload = json.loads(note.payload)
                break
        assert payload is not None, "expected a tape_score_inserted notification"
        assert payload == {"user_id": 1, "document_id": 1}
