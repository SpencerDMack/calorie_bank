# Database helpers for Calorie Bank
from __future__ import annotations

import os
import re
import shutil
import sqlite3
from typing import Optional

import pandas as pd

LEGACY_DB_PATH = os.path.join(os.path.dirname(__file__), "calorie_bank.db")
USER_DB_DIR = os.path.join(os.path.dirname(__file__), "user_dbs")


def _safe_user_id(user_id: str) -> str:
    cleaned = user_id.strip().lower()
    cleaned = re.sub(r"[^a-z0-9_-]+", "_", cleaned)
    cleaned = cleaned.strip("_")
    return cleaned or "user"


def get_db_path(user_id: str) -> str:
    os.makedirs(USER_DB_DIR, exist_ok=True)
    safe_id = _safe_user_id(user_id)
    return os.path.join(USER_DB_DIR, f"calorie_bank_{safe_id}.db")


def legacy_db_exists() -> bool:
    return os.path.exists(LEGACY_DB_PATH)


def user_db_exists(user_id: str) -> bool:
    return os.path.exists(get_db_path(user_id))


def import_legacy_db(user_id: str) -> None:
    if not legacy_db_exists():
        return
    target = get_db_path(user_id)
    if os.path.exists(target):
        return
    os.makedirs(USER_DB_DIR, exist_ok=True)
    shutil.copy2(LEGACY_DB_PATH, target)


def get_connection(user_id: str) -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path(user_id))
    conn.row_factory = sqlite3.Row
    return conn


def create_tables(user_id: str) -> None:
    with get_connection(user_id) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                age INTEGER NOT NULL,
                gender TEXT NOT NULL,
                height_cm REAL NOT NULL,
                weight_lbs REAL NOT NULL,
                activity_level REAL NOT NULL,
                maintenance_calories REAL NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                calories_consumed REAL NOT NULL,
                daily_balance REAL NOT NULL,
                running_balance REAL NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS weekly_checkins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                actual_weight_lbs REAL
            );
            """
        )
        _ensure_profile_columns(conn)


def _ensure_profile_columns(conn: sqlite3.Connection) -> None:
    existing_cols = {
        row["name"] for row in conn.execute("PRAGMA table_info(profile);").fetchall()
    }
    if "goal_type" not in existing_cols:
        conn.execute("ALTER TABLE profile ADD COLUMN goal_type TEXT;")
    if "target_weight_lbs" not in existing_cols:
        conn.execute("ALTER TABLE profile ADD COLUMN target_weight_lbs REAL;")




def get_profile(user_id: str) -> Optional[dict]:
    with get_connection(user_id) as conn:
        row = conn.execute(
            "SELECT * FROM profile ORDER BY id DESC LIMIT 1;"
        ).fetchone()
        return dict(row) if row else None


def save_profile(
    user_id: str,
    age: int,
    gender: str,
    height_cm: float,
    weight_lbs: float,
    activity_level: float,
    maintenance_calories: float,
    goal_type: str | None,
    target_weight_lbs: float | None,
) -> None:
    existing = get_profile(user_id)
    with get_connection(user_id) as conn:
        if existing:
            conn.execute(
                """
                UPDATE profile
                SET age = ?, gender = ?, height_cm = ?, weight_lbs = ?,
                    activity_level = ?, maintenance_calories = ?,
                    goal_type = ?, target_weight_lbs = ?
                WHERE id = ?;
                """,
                (
                    age,
                    gender,
                    height_cm,
                    weight_lbs,
                    activity_level,
                    maintenance_calories,
                    goal_type,
                    target_weight_lbs,
                    existing["id"],
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO profile
                (age, gender, height_cm, weight_lbs, activity_level, maintenance_calories, goal_type, target_weight_lbs)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    age,
                    gender,
                    height_cm,
                    weight_lbs,
                    activity_level,
                    maintenance_calories,
                    goal_type,
                    target_weight_lbs,
                ),
            )


def get_daily_logs(user_id: str) -> pd.DataFrame:
    with get_connection(user_id) as conn:
        df = pd.read_sql_query("SELECT * FROM daily_logs ORDER BY date;", conn)
    return df


def get_log_by_date(user_id: str, date_str: str) -> Optional[dict]:
    with get_connection(user_id) as conn:
        row = conn.execute(
            "SELECT * FROM daily_logs WHERE date = ?;", (date_str,)
        ).fetchone()
        return dict(row) if row else None


def upsert_daily_log(
    user_id: str, date_str: str, calories_consumed: float, daily_balance: float
) -> None:
    with get_connection(user_id) as conn:
        conn.execute(
            """
            INSERT INTO daily_logs (date, calories_consumed, daily_balance, running_balance)
            VALUES (?, ?, ?, 0)
            ON CONFLICT(date) DO UPDATE SET
                calories_consumed = excluded.calories_consumed,
                daily_balance = excluded.daily_balance;
            """,
            (date_str, calories_consumed, daily_balance),
        )


def delete_daily_log(user_id: str, date_str: str) -> None:
    with get_connection(user_id) as conn:
        conn.execute("DELETE FROM daily_logs WHERE date = ?;", (date_str,))


def get_weekly_checkins(user_id: str) -> pd.DataFrame:
    with get_connection(user_id) as conn:
        df = pd.read_sql_query("SELECT * FROM weekly_checkins ORDER BY date;", conn)
    return df


def upsert_weekly_checkin(user_id: str, date_str: str, actual_weight_lbs: float) -> None:
    with get_connection(user_id) as conn:
        conn.execute(
            """
            INSERT INTO weekly_checkins (date, actual_weight_lbs)
            VALUES (?, ?)
            ON CONFLICT(date) DO UPDATE SET
                actual_weight_lbs = excluded.actual_weight_lbs;
            """,
            (date_str, actual_weight_lbs),
        )


def delete_weekly_checkin(user_id: str, date_str: str) -> None:
    with get_connection(user_id) as conn:
        conn.execute("DELETE FROM weekly_checkins WHERE date = ?;", (date_str,))


def update_running_balances(user_id: str) -> None:
    df = get_daily_logs(user_id)
    if df.empty:
        return
    df = df.sort_values("date")
    running = 0.0
    with get_connection(user_id) as conn:
        for _, row in df.iterrows():
            running += float(row["daily_balance"])
            conn.execute(
                "UPDATE daily_logs SET running_balance = ? WHERE id = ?;",
                (running, int(row["id"])),
            )


def update_all_daily_balances(user_id: str, maintenance: float) -> None:
    df = get_daily_logs(user_id)
    if df.empty:
        return
    with get_connection(user_id) as conn:
        for _, row in df.iterrows():
            daily_balance = maintenance - float(row["calories_consumed"])
            conn.execute(
                "UPDATE daily_logs SET daily_balance = ? WHERE id = ?;",
                (daily_balance, int(row["id"])),
            )
    update_running_balances(user_id)


def get_weekly_deficit_so_far(
    user_id: str, start_date: str, end_date_exclusive: str
) -> float:
    with get_connection(user_id) as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(daily_balance), 0) AS total_deficit
            FROM daily_logs
            WHERE date >= ? AND date < ?;
            """,
            (start_date, end_date_exclusive),
        ).fetchone()
        return float(row["total_deficit"]) if row else 0.0
