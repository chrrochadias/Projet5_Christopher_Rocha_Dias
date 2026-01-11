#!/usr/bin/env python3
"""
migrate.py
----------
Lit un dataset CSV/JSON/JSONL et migre les données vers MongoDB (via Docker).

Objectifs "Data Engineering / prod-ready":
- Reproductible (Docker)
- Idempotent (upsert sur une clé unique stable: patient_id)
- Performant (bulk_write par batch)
- Typé / nettoyé (NaN -> None, casting, normalisation)
- Indexation (unique + indexes utiles)
"""

import os
import math
import hashlib
from datetime import datetime, date
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd
from pymongo import MongoClient, UpdateOne
from pymongo.collection import Collection
from pymongo.errors import BulkWriteError


def env(name: str, default: Optional[str] = None) -> str:
    """Get environment variable or default, raise if missing."""
    value = os.getenv(name, default)
    if value is None or value == "":
        raise RuntimeError(f"Missing env var: {name}")
    return value


def build_mongo_uri() -> str:
    """
    Build a Mongo URI for an application user created in the target DB.
    Example: mongodb://user:pwd@mongodb:27017/medical?authSource=medical
    """
    host = env("MONGO_HOST", "localhost")
    port = env("MONGO_PORT", "27017")
    user = env("MONGO_APP_USER")
    pwd = env("MONGO_APP_PASSWORD")
    db = env("MONGO_DB", "medical")
    return f"mongodb://{user}:{pwd}@{host}:{port}/{db}?authSource={db}"


def read_dataset(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.where(pd.notnull(df), None)
    return df


def safe_int(v: Any) -> Optional[int]:
    """Safely casts to int, returning None on failure"""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def safe_float(v: Any) -> Optional[float]:
    """Safely casts to float, returning None on failure"""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def safe_date_iso(v: Any) -> Optional[str]:
    """
    Return YYYY-MM-DD or None.
    Accepts already-ISO strings, datetime/date, etc.
    """
    if v is None:
        return None

    if isinstance(v, (datetime, date)):
        return v.strftime("%Y-%m-%d")

    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        # try parse flexible (handles '2024-01-31')
        try:
            dt = pd.to_datetime(s, errors="coerce")
            if pd.isna(dt):
                return None
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return None

    # try pandas parse for other types
    try:
        dt = pd.to_datetime(v, errors="coerce")
        if pd.isna(dt):
            return None
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def normalize_name(name: Any) -> Dict[str, Optional[str]]:
    """
    Normalize name with:
    - full: Title Cased (best-effort)
    - normalized: lowercase (useful for searching)
    """
    if name is None:
        return {"full": None, "normalized": None}

    s = str(name)
    clean = " ".join(s.split()).strip()
    if not clean:
        return {"full": None, "normalized": None}

    return {"full": clean.title(), "normalized": clean.lower()}


def generate_patient_id(name: Any, admission_date: Any) -> str:
    """
    Generate a stable identifier from name + admission date.
    This makes the migration idempotent even without an explicit ID in CSV.
    """
    n = (str(name).strip() if name is not None else "").lower()
    d = safe_date_iso(admission_date) or ""
    raw = f"{n}|{d}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def map_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map one CSV row -> MongoDB document.
    Uses the dataset columns provided in your sample:
      Name, Age, Gender, Blood Type, Medical Condition, Date of Admission,
      Doctor, Hospital, Insurance Provider, Billing Amount, Room Number,
      Admission Type, Discharge Date, Medication, Test Results
    """
    now = datetime.utcnow()

    patient_id = generate_patient_id(
        row.get("Name"),
        row.get("Date of Admission"),
    )

    doc: Dict[str, Any] = {
        "patient_id": patient_id,
        "name": normalize_name(row.get("Name")),
        "age": safe_int(row.get("Age")),
        "gender": row.get("Gender"),
        "blood_type": row.get("Blood Type"),
        "medical_condition": row.get("Medical Condition"),
        "admission": {
            "type": row.get("Admission Type"),
            "date": safe_date_iso(row.get("Date of Admission")),
            "discharge_date": safe_date_iso(row.get("Discharge Date")),
            "room_number": safe_int(row.get("Room Number")),
        },
        "doctor": row.get("Doctor"),
        "hospital": row.get("Hospital"),
        "insurance_provider": row.get("Insurance Provider"),
        "billing_amount": (
            round(safe_float(row.get("Billing Amount")), 2)
            if safe_float(row.get("Billing Amount")) is not None
            else None
        ),
        "medication": row.get("Medication"),
        "test_results": row.get("Test Results"),
        "updated_at": now,
        # created_at should only be set on insert, not on every upsert
        # we will apply it using $setOnInsert below
    }

    return doc


def chunker(seq: List[Dict[str, Any]], size: int) -> Iterable[List[Dict[str, Any]]]:
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def ensure_indexes(coll: Collection) -> None:
    """
    Create indexes (idempotent operation in Mongo).
    """
    coll.create_index([("patient_id", 1)], unique=True)
    coll.create_index([("name.normalized", 1)])
    coll.create_index([("medical_condition", 1)])
    coll.create_index([("admission.date", 1)])


def main() -> None:
    dataset_path = env("DATASET_PATH", "/app/data/dataset.csv")
    db_name = env("MONGO_DB", "medical")
    coll_name = env("COLLECTION_NAME", "patients")
    batch_size = int(env("BATCH_SIZE", "1000"))

    uri = build_mongo_uri()
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    db = client[db_name]
    coll = db[coll_name]

    df = read_dataset(dataset_path)

    # Basic validation (expected columns)
    expected = [
        "Name",
        "Age",
        "Gender",
        "Blood Type",
        "Medical Condition",
        "Date of Admission",
        "Doctor",
        "Hospital",
        "Insurance Provider",
        "Billing Amount",
        "Room Number",
        "Admission Type",
        "Discharge Date",
        "Medication",
        "Test Results",
    ]
    missing = [c for c in expected if c not in df.columns]
    if missing:
        raise RuntimeError(f"Missing expected columns: {missing}. Found: {list(df.columns)}")

    ensure_indexes(coll)

    records: List[Dict[str, Any]] = df.to_dict(orient="records")
    total = len(records)
    print(f"Loaded {total} records from {dataset_path}")

    processed = 0
    total_upserted = 0

    # Iterates batches; upserts mapped rows; reports results
    for batch in chunker(records, batch_size):
        ops: List[UpdateOne] = []

        for row in batch:
            doc = map_row(row)

            # Skip if we somehow failed to produce an id
            if not doc.get("patient_id"):
                continue

            # created_at set only when inserting (not updating)
            now = doc["updated_at"]
            ops.append(
                UpdateOne(
                    {"patient_id": doc["patient_id"]},
                    {
                        "$set": doc,
                        "$setOnInsert": {"created_at": now},
                    },
                    upsert=True,
                )
            )

        if not ops:
            continue

        try:
            res = coll.bulk_write(ops, ordered=False)
            processed += len(ops)
            total_upserted += len(res.upserted_ids or {})
            print(
                f"Batch: ops={len(ops)} matched={res.matched_count} "
                f"modified={res.modified_count} upserted={len(res.upserted_ids or {})}"
            )
        except BulkWriteError as e:
            # In a production pipeline you might log details and continue.
            # Here we print and re-raise to fail fast.
            print("BulkWriteError details:", e.details)
            raise

    print(f"Done. Processed ops: {processed} / {total}. Total inserted (upserts): {total_upserted}")
    client.close()


if __name__ == "__main__":
    main()
