from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Dict, Literal
import re

app = FastAPI()

# ---- Data model (strict) ----
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

# ---- Aggregated storage in memory (demo) ----
# counts[day]["P"]["P2"] = 5, etc.
counts: Dict[str, Dict[str, Dict[str, int]]] = {}

def valid_day(day: str) -> bool:
    return re.match(r"^\d{4}-\d{2}-\d{2}$", day) is not None

def inc(day: str, metric: str, bucket: str):
    counts.setdefault(day, {})
    counts[day].setdefault(metric, {})
    counts[day][metric][bucket] = counts[day][metric].get(bucket, 0) + 1

@app.post("/upload")
def upload(payload: Payload):
    # Strict date check
    if not valid_day(payload.day):
        return {"ok": False, "error": "bad day format"}

    # Increment aggregate counters ONLY (no raw storage)
    inc(payload.day, "P", payload.buckets.P)
    inc(payload.day, "L", payload.buckets.L)
    inc(payload.day, "B", payload.buckets.B)
    inc(payload.day, "C", payload.buckets.C)

    return {"ok": True}

@app.get("/counts/{day}")
def get_counts(day: str):
    return counts.get(day, {})