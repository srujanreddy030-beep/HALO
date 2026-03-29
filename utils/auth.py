import sqlite3
import hashlib
import os
from datetime import datetime, timezone
from typing import Optional, Tuple


def get_current_time_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def hash_password(password: str) -> str:
    """Generate a simple SHA-256 hash with a fixed salt for simplicity, 
    or just use hashlib's pbkdf2 if preferred. Here we use pbkdf2_hmac."""
    # A random salt is better, but this works for basic app demonstration
    salt = b"halo_dashboard_salt_9283"
    key = hashlib.pbkdf2_hmac(
        'sha256', 
        password.encode('utf-8'), 
        salt, 
        100000
    )
    return key.hex()


def verify_password(stored_hash: str, provided_password: str) -> bool:
    """Verify a password against the stored hash."""
    return hash_password(provided_password) == stored_hash


def create_user(db_path: str, username: str, password: str, email: str = "", phone_number: str = "", company: str = "") -> Tuple[bool, str]:
    """
    Attempt to create a new user in the database.
    Returns (success, message).
    """
    username = username.strip().lower()
    if not username or not password:
        return False, "Username and password cannot be empty."

    hashed = hash_password(password)
    now = get_current_time_iso()

    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT INTO users (username, password_hash, created_at, email, phone_number, company) VALUES (?, ?, ?, ?, ?, ?)",
                (username, hashed, now, email, phone_number, company),
            )
            conn.commit()
            return True, "User created successfully."
    except sqlite3.IntegrityError:
        return False, "User already exists. Please login."
    except Exception as e:
        return False, f"Database error: {e}"


def authenticate_user(db_path: str, username: str, password: str) -> bool:
    """
    Check if the user exists and the password matches.
    Returns True if valid, False otherwise.
    """
    username = username.strip().lower()
    
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT password_hash FROM users WHERE username = ?",
                (username,)
            ).fetchone()
            
            if row:
                stored_hash = row["password_hash"]
                return verify_password(stored_hash, password)
            return False
    except Exception:
        return False
