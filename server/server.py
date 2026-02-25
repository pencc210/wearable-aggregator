from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Dict, Literal
import re
import sqlite3
import os

app = FastAPI()

# ---------- Strict schema ----------
BucketP = Literal["P0","P1","P2","P3","P4"]
BucketL = Literal["L0","L1","L2","L3","L4"]
BucketB = Literal["B0","B1","B2","B3"]
BucketC = Literal["C0","C1","C2","C3","C4"]

class Buckets(BaseModel):
    P: BucketP
    L: BucketL
    B: BucketB
    C: BucketC

class Payload(BaseModel):
    schema_version: int = Field(1)
    day: str
    buckets: Buckets

def valid_day(day: str) -> bool:
    return re.match(r"^\d{4}-\d{2}-\d{2}$", day) is not None


# ---------- SQLite storage ----------
DB_PATH = os.environ.get("DB_PATH", "counts.db")

def get_conn():
    # check_same_thread=False allows FastAPI threads to use the connection safely
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS agg_counts (
            day TEXT NOT NULL,
            metric TEXT NOT NULL,
            bucket TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (day, metric, bucket)
        );
    """)
    conn.commit()
    conn.close()

init_db()

def inc(day: str, metric: str, bucket: str):
    conn = get_conn()
    cur = conn.cursor()

    # UPSERT: insert row if missing, otherwise increment
    cur.execute("""
        INSERT INTO agg_counts(day, metric, bucket, count)
        VALUES (?, ?, ?, 1)
        ON CONFLICT(day, metric, bucket)
        DO UPDATE SET count = count + 1;
    """, (day, metric, bucket))

    conn.commit()
    conn.close()

def get_day_counts(day: str) -> Dict[str, Dict[str, int]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT metric, bucket, count
        FROM agg_counts
        WHERE day = ?;
    """, (day,))
    rows = cur.fetchall()
    conn.close()

    out: Dict[str, Dict[str, int]] = {}
    for r in rows:
        out.setdefault(r["metric"], {})
        out[r["metric"]][r["bucket"]] = int(r["count"])
    return out


# ---------- API ----------
@app.post("/upload")
def upload(payload: Payload):
    if payload.schema_version != 1:
        return {"ok": False, "error": "bad schema_version"}

    if not valid_day(payload.day):
        return {"ok": False, "error": "bad day format"}

    # Increment aggregate counters ONLY (no raw storage)
    inc(payload.day, "P", payload.buckets.P)
    inc(payload.day, "L", payload.buckets.L)
    inc(payload.day, "B", payload.buckets.B)
    inc(payload.day, "C", payload.buckets.C)

    return {"ok": True}

@app.get("/counts/{day}")
def counts(day: str):
    if not valid_day(day):
        return {}
    return get_day_counts(day)

@app.get("/health")
def health():
    return {"ok": True, "db": DB_PATH}