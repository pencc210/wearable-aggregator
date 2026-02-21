import os
import json
import shutil
import re
import requests

# ---- Folder paths ----
INCOMING = "incoming"
SENT = "sent"
FAILED = "failed"

# ---- Server endpoint ----
SERVER_URL = "https://worker-health-aggregator.onrender.com/upload"

# ---- Allowed bucket values ----
ALLOWED_BUCKETS = {
    "P": ["P0", "P1", "P2", "P3", "P4"],
    "L": ["L0", "L1", "L2", "L3", "L4"],
    "B": ["B0", "B1", "B2", "B3"],
    "C": ["C0", "C1", "C2", "C3", "C4"]
}

# ---- Validation ----
def validate_json(data):

    # Top level keys must match exactly
    if set(data.keys()) != {"schema_version", "day", "buckets"}:
        raise ValueError("Invalid top-level keys")

    if data["schema_version"] != 1:
        raise ValueError("Unsupported schema version")

    # Validate date format YYYY-MM-DD
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", data["day"]):
        raise ValueError("Invalid date format")

    buckets = data["buckets"]

    # Must contain exactly P, L, B, C
    if set(buckets.keys()) != {"P", "L", "B", "C"}:
        raise ValueError("Invalid bucket keys")

    # Validate each bucket value
    for key, value in buckets.items():
        if value not in ALLOWED_BUCKETS[key]:
            raise ValueError(f"Invalid value for {key}: {value}")

    return True


# ---- Main processing ----
def process_files():

    files = os.listdir(INCOMING)

    for filename in files:

        if not filename.endswith(".json"):
            continue

        filepath = os.path.join(INCOMING, filename)

        try:
            # 1. Load JSON
            with open(filepath, "r") as f:
                data = json.load(f)

            # 2. Validate strictly
            validate_json(data)

            # 3. Send to aggregation server
            response = requests.post(SERVER_URL, json=data, timeout=5)

            if response.status_code != 200:
                raise ValueError("Server error")

            resp_json = response.json()

            if not resp_json.get("ok"):
                raise ValueError("Server rejected payload")

            # 4. Move to sent only if upload successful
            shutil.move(filepath, os.path.join(SENT, filename))
            print(f"Uploaded + moved {filename} to sent/")

        except Exception as e:
            print(f"Rejected file {filename}: {e}")
            shutil.move(filepath, os.path.join(FAILED, filename))
            print(f"Moved {filename} to failed/")


if __name__ == "__main__":
    process_files()