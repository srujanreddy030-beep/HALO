import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS incidents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_utc TEXT NOT NULL,
  track_id INTEGER,
  severity TEXT NOT NULL,
  incident_type TEXT NOT NULL,
  message TEXT NOT NULL,
  image_path TEXT
);

CREATE INDEX IF NOT EXISTS idx_incidents_ts ON incidents(ts_utc);
CREATE INDEX IF NOT EXISTS idx_incidents_type ON incidents(incident_type);

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  email TEXT,
  phone_number TEXT,
  company TEXT
);

CREATE TABLE IF NOT EXISTS active_session (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  username TEXT
);
"""


@dataclass
class Incident:
    ts_utc: str
    track_id: Optional[int]
    severity: str
    incident_type: str
    message: str
    image_path: Optional[str]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def init_db(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        
        # Dynamically add columns for existing databases
        for col in ["email", "phone_number", "company"]:
            try:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT")
            except sqlite3.OperationalError:
                pass  # Column likely exists
                
        try:
            conn.execute("ALTER TABLE incidents ADD COLUMN owner_username TEXT")
        except sqlite3.OperationalError:
            pass
            
        conn.commit()

def set_active_user(db_path: str, username: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("INSERT OR REPLACE INTO active_session (id, username) VALUES (1, ?)", (username,))
        # Claim any legacy incidents that have no owner (recorded before multi-tenant was added)
        conn.execute("UPDATE incidents SET owner_username = ? WHERE owner_username IS NULL", (username,))
        conn.commit()

def get_active_user(db_path: str) -> Optional[str]:
    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute("SELECT username FROM active_session WHERE id = 1").fetchone()
            if row:
                return row[0]
    except sqlite3.OperationalError:
        pass
    return None


def log_incident(
    db_path: str,
    *,
    track_id: Optional[int],
    severity: str,
    incident_type: str,
    message: str,
    image_path: Optional[str] = None,
    ts_utc: Optional[str] = None,
    owner_username: Optional[str] = None,
) -> None:
    ts_utc = ts_utc or utc_now_iso()
    
    # Auto-resolve owner if not explicitly passed
    if owner_username is None:
        owner_username = get_active_user(db_path)
        
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO incidents (ts_utc, track_id, severity, incident_type, message, image_path, owner_username)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (ts_utc, track_id, severity, incident_type, message, image_path, owner_username),
        )
        conn.commit()


def fetch_recent(db_path: str, limit: int = 200, owner_username: Optional[str] = None) -> List[Dict[str, Any]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        
        query = """
            SELECT id, ts_utc, track_id, severity, incident_type, message, image_path, owner_username
            FROM incidents
        """
        params = []
        if owner_username:
            query += " WHERE owner_username = ?"
            params.append(owner_username)
            
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        
        rows = conn.execute(query, tuple(params)).fetchall()
    return [dict(r) for r in rows]


def stats(db_path: str, owner_username: Optional[str] = None) -> Dict[str, Any]:
    with sqlite3.connect(db_path) as conn:
        where_clause = ""
        params = []
        if owner_username:
            where_clause = "WHERE owner_username = ?"
            params.append(owner_username)
            
        total_query = f"SELECT COUNT(*) FROM incidents {where_clause}"
        sev_query = f"SELECT severity, COUNT(*) FROM incidents {where_clause} GROUP BY severity"
        type_query = f"SELECT incident_type, COUNT(*) FROM incidents {where_clause} GROUP BY incident_type"
        
        total = conn.execute(total_query, tuple(params)).fetchone()[0]
        by_sev = conn.execute(sev_query, tuple(params)).fetchall()
        by_type = conn.execute(type_query, tuple(params)).fetchall()
        
    return {
        "total": total,
        "by_severity": {k: v for (k, v) in by_sev},
        "by_type": {k: v for (k, v) in by_type},
    }


def delete_all_incidents(db_path: str, owner_username: Optional[str] = None) -> int:
    with sqlite3.connect(db_path) as conn:
        if owner_username:
            cur = conn.execute("DELETE FROM incidents WHERE owner_username = ?", (owner_username,))
        else:
            cur = conn.execute("DELETE FROM incidents")
        conn.commit()
        return int(cur.rowcount or 0)

