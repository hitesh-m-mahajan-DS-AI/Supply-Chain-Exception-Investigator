"""SQLite persistence; immutable investigations and append-only analyst notes."""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4
import json
import sqlite3

ROOT=Path(__file__).resolve().parents[1]
LOCK=Lock()


@contextmanager
def connection():
    path=ROOT/"runtime/investigations.sqlite3"
    path.parent.mkdir(parents=True,exist_ok=True)
    with LOCK:
        db=sqlite3.connect(path)
        db.row_factory=sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("CREATE TABLE IF NOT EXISTS investigations(id TEXT PRIMARY KEY, created_at TEXT, case_id TEXT, question TEXT, payload TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS reviews(id TEXT PRIMARY KEY, investigation_id TEXT REFERENCES investigations(id), created_at TEXT, disposition TEXT, note TEXT)")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


def save(run):
    with connection() as db:
        db.execute("INSERT INTO investigations VALUES(?,?,?,?,?)",[run["id"],run["created_at"],run["request"]["case_id"],run["request"]["question"],json.dumps(run,allow_nan=False)])


def get(run_id):
    with connection() as db:
        row=db.execute("SELECT payload FROM investigations WHERE id=?",[run_id]).fetchone()
    return json.loads(row[0]) if row else None


def reviews(run_id):
    with connection() as db:
        return [dict(r) for r in db.execute("SELECT * FROM reviews WHERE investigation_id=? ORDER BY created_at",[run_id])]


def review(run_id, request):
    row={"id":str(uuid4()),"investigation_id":run_id,"created_at":datetime.now(timezone.utc).isoformat(),**request.model_dump()}
    with connection() as db:
        db.execute("INSERT INTO reviews VALUES(?,?,?,?,?)",[row[k] for k in ["id","investigation_id","created_at","disposition","note"]])
    return row


def history():
    with connection() as db:
        rows=db.execute("SELECT id,created_at,case_id,question,payload FROM investigations ORDER BY created_at DESC LIMIT 100").fetchall()
        result=[]
        for row in rows:
            run=json.loads(row["payload"])
            latest=db.execute("SELECT disposition FROM reviews WHERE investigation_id=? ORDER BY created_at DESC LIMIT 1",[row["id"]]).fetchone()
            result.append({"id":row["id"],"created_at":row["created_at"],"case_id":row["case_id"],"question":row["question"],
                           "state":run["generation"]["state"],"mode":run["request"]["mode"],
                           "review":latest[0] if latest else "unreviewed"})
    return result
