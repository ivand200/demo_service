"""Product pricing API.

One endpoint returns the final price of a product after a sale discount.
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

DB_PATH = Path(os.environ.get("DEMO_DB", "pricing.sqlite"))
LOG_PATH = Path(os.environ.get("DEMO_LOG", "logs/app.jsonl"))

app = FastAPI(title="pricing", version="1.0.0")


class PriceRequest(BaseModel):
    product: str
    sale_rate: float


def release() -> str:
    """Short git revision of the running code."""
    try:
        done = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except OSError:
        return "unknown"
    return done.stdout.strip() or "unknown"


RELEASE = release()


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def seed() -> None:
    """Create the product table on first start. Price is 10.00 + index."""
    connection = connect()
    connection.execute(
        "CREATE TABLE IF NOT EXISTS products ("
        " product TEXT PRIMARY KEY, price REAL NOT NULL)"
    )
    count = connection.execute("SELECT COUNT(*) AS n FROM products").fetchone()["n"]
    if count == 0:
        rows = [(f"product_{i:03d}", round(10.0 + i, 2)) for i in range(100)]
        connection.executemany(
            "INSERT INTO products (product, price) VALUES (?, ?)", rows
        )
        connection.commit()
    connection.close()


def final_price(base_price: float, sale_rate: float) -> float:
    """Apply the sale discount, given in percent."""
    return round(base_price * (1 - sale_rate / 100), 2)


def json_safe(value):
    """Turn non-finite floats into strings, so each log line stays valid JSON."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value


def write_log(record: dict) -> None:
    """Append one JSON object to the request log."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
        "release": RELEASE,
    }
    entry.update({key: json_safe(value) for key, value in record.items()})
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, allow_nan=False) + "\n")


seed()


@app.get("/health")
def health() -> dict:
    connection = connect()
    count = connection.execute("SELECT COUNT(*) AS n FROM products").fetchone()["n"]
    connection.close()
    return {"ok": True, "products": count, "release": RELEASE}


@app.post("/price")
def price(request: PriceRequest) -> dict:
    connection = connect()
    row = connection.execute(
        "SELECT price FROM products WHERE product = ?", (request.product,)
    ).fetchone()
    connection.close()

    if row is None:
        write_log(
            {
                "route": "POST /price",
                "status": 404,
                "product": request.product,
                "sale_rate": request.sale_rate,
            }
        )
        raise HTTPException(
            status_code=404, detail=f"unknown product: {request.product}"
        )

    base_price = row["price"]
    final = final_price(base_price, request.sale_rate)
    write_log(
        {
            "route": "POST /price",
            "status": 200,
            "product": request.product,
            "sale_rate": request.sale_rate,
            "base_price": base_price,
            "final_price": final,
        }
    )
    return {
        "product": request.product,
        "base_price": base_price,
        "sale_rate": request.sale_rate,
        "final_price": final,
    }
