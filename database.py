import sqlite3
from contextlib import contextmanager
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATABASE = str(BASE_DIR / "votelock.db")


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_connection():
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _columns(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _add_column(conn, table, column, definition):
    if column not in _columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        is_verified INTEGER DEFAULT 0,
        otp_hash TEXT,
        otp_expiry TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        symbol TEXT,
        party TEXT,
        description TEXT,
        status TEXT DEFAULT 'Active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS voters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        voter_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        email TEXT,
        department TEXT,
        username TEXT UNIQUE,
        password_hash TEXT,
        qr_token TEXT UNIQUE,
        has_voted INTEGER DEFAULT 0,
        image_path TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS votes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id INTEGER NOT NULL,
        voter_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(candidate_id) REFERENCES candidates(id)
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL,
        voter_id TEXT,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # Safe upgrades for databases created during Review 0/Review 1.
    _add_column(conn, "candidates", "party", "TEXT")
    _add_column(conn, "voters", "image_path", "TEXT")
    _add_column(conn, "votes", "voter_id", "TEXT")

    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_voters_voter_id ON voters(voter_id)",
        "CREATE INDEX IF NOT EXISTS idx_voters_qr_token ON voters(qr_token)",
        "CREATE INDEX IF NOT EXISTS idx_votes_candidate ON votes(candidate_id)",
        "CREATE INDEX IF NOT EXISTS idx_votes_voter ON votes(voter_id)",
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at)",
    ]
    for sql in indexes:
        cur.execute(sql)

    conn.commit()
    conn.close()


def get_dashboard_stats():
    conn = get_db()
    total_voters = conn.execute("SELECT COUNT(*) FROM voters").fetchone()[0]
    total_candidates = conn.execute(
        "SELECT COUNT(*) FROM candidates WHERE status='Active'"
    ).fetchone()[0]
    total_votes = conn.execute("SELECT COUNT(*) FROM votes").fetchone()[0]
    voted = conn.execute(
        "SELECT COUNT(*) FROM voters WHERE has_voted=1"
    ).fetchone()[0]
    pending = total_voters - voted
    turnout = round(voted / total_voters * 100, 1) if total_voters else 0
    conn.close()
    return {
        "voters": total_voters,
        "candidates": total_candidates,
        "votes": total_votes,
        "pending_voters": pending,
        "voted_voters": voted,
        "turnout": turnout,
    }


def add_audit_log(event_type, description, voter_id=None):
    with db_connection() as conn:
        conn.execute(
            "INSERT INTO audit_logs(event_type,voter_id,description) VALUES(?,?,?)",
            (event_type, voter_id, description),
        )


def get_recent_logs(limit=12):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return rows


def get_all_voters():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM voters ORDER BY created_at DESC, id DESC"
    ).fetchall()
    conn.close()
    return rows


def get_voter(voter_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM voters WHERE voter_id=?", (voter_id,)
    ).fetchone()
    conn.close()
    return row


def get_voter_by_username(username):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM voters WHERE UPPER(username)=UPPER(?)", (username,)
    ).fetchone()
    conn.close()
    return row


def delete_voter(voter_id):
    with db_connection() as conn:
        row = conn.execute(
            "SELECT has_voted FROM voters WHERE voter_id=?", (voter_id,)
        ).fetchone()
        if not row:
            return False, "Voter not found."
        if row["has_voted"]:
            return False, "This voter has already voted and cannot be deleted."
        conn.execute("DELETE FROM voters WHERE voter_id=?", (voter_id,))
        return True, "Voter deleted successfully."


def get_all_candidates():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM candidates ORDER BY created_at DESC, id DESC"
    ).fetchall()
    conn.close()
    return rows


def get_active_candidates():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM candidates WHERE status='Active' ORDER BY id"
    ).fetchall()
    conn.close()
    return rows


def get_candidate(candidate_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM candidates WHERE candidate_id=?", (candidate_id,)
    ).fetchone()
    conn.close()
    return row


def delete_candidate(candidate_id):
    with db_connection() as conn:
        row = conn.execute(
            "SELECT id FROM candidates WHERE candidate_id=?", (candidate_id,)
        ).fetchone()
        if not row:
            return False, "Candidate not found."
        votes = conn.execute(
            "SELECT COUNT(*) FROM votes WHERE candidate_id=?", (row["id"],)
        ).fetchone()[0]
        if votes:
            return False, "This candidate already has votes and cannot be deleted."
        conn.execute("DELETE FROM candidates WHERE candidate_id=?", (candidate_id,))
        return True, "Candidate deleted successfully."


def voter_has_voted(voter_id):
    row = get_voter(voter_id)
    return bool(row and row["has_voted"])


def mark_voter_as_voted(voter_id):
    with db_connection() as conn:
        conn.execute("UPDATE voters SET has_voted=1 WHERE voter_id=?", (voter_id,))
