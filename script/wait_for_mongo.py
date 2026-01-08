#!/usr/bin/env python3
from __future__ import annotations

import os
import time
import argparse
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError, OperationFailure


def env(name: str, default: str | None = None) -> str:
    v = os.getenv(name, default)
    if v is None or v == "":
        raise RuntimeError(f"Missing env var: {name}")
    return v


def build_uri() -> str:
    host = env("MONGO_HOST", "mongodb")
    port = env("MONGO_PORT", "27017")
    user = env("MONGO_APP_USER")
    pwd = env("MONGO_APP_PASSWORD")
    db = env("MONGO_DB", "medical")
    return f"mongodb://{user}:{pwd}@{host}:{port}/{db}?authSource={db}"


def wait_for_ping(client: MongoClient, timeout_s: int, interval_s: float) -> None:
    deadline = time.time() + timeout_s
    last_err: Exception | None = None

    while time.time() < deadline:
        try:
            client.admin.command("ping")
            return
        except (ServerSelectionTimeoutError, OperationFailure) as e:
            last_err = e
            time.sleep(interval_s)

    raise RuntimeError(f"Mongo not ready (ping) after {timeout_s}s. Last error: {last_err}")


def wait_for_data(db, collection: str, min_docs: int, timeout_s: int, interval_s: float) -> int:
    deadline = time.time() + timeout_s
    last_count = 0

    while time.time() < deadline:
        last_count = db[collection].count_documents({})
        if last_count >= min_docs:
            return last_count
        time.sleep(interval_s)

    raise RuntimeError(
        f"Mongo ready but data check failed: collection '{collection}' has {last_count} docs, "
        f"expected >= {min_docs} after {timeout_s}s."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Wait for MongoDB readiness (and optionally data presence).")
    parser.add_argument("--timeout", type=int, default=int(os.getenv("WAIT_TIMEOUT", "60")))
    parser.add_argument("--interval", type=float, default=float(os.getenv("WAIT_INTERVAL", "1.5")))
    parser.add_argument("--check-data", action="store_true", help="Also check collection contains data.")
    parser.add_argument("--collection", default=os.getenv("COLLECTION_NAME", "patients"))
    parser.add_argument("--min-docs", type=int, default=int(os.getenv("MIN_DOCS", "1")))
    args = parser.parse_args()

    uri = build_uri()
    db_name = env("MONGO_DB", "medical")

    client = MongoClient(uri, serverSelectionTimeoutMS=3000)

    wait_for_ping(client, timeout_s=args.timeout, interval_s=args.interval)
    print("✅ Mongo ping OK")

    if args.check_data:
        db = client[db_name]
        count = wait_for_data(
            db,
            collection=args.collection,
            min_docs=args.min_docs,
            timeout_s=args.timeout,
            interval_s=args.interval,
        )
        print(f"✅ Data check OK: {args.collection} has {count} docs (>= {args.min_docs})")

    client.close()


if __name__ == "__main__":
    main()
