"""Behaviour checks for the pricing API. HTTP is the tested seam."""

import json
import os
import tempfile
from pathlib import Path

_RUNTIME = Path(tempfile.mkdtemp(prefix="demo-service-test-"))
os.environ["DEMO_DB"] = str(_RUNTIME / "pricing.sqlite")
os.environ["DEMO_LOG"] = str(_RUNTIME / "app.jsonl")

from fastapi.testclient import TestClient  # noqa: E402

from app import app  # noqa: E402

client = TestClient(app)


def test_health_reports_all_products() -> None:
    # GIVEN a freshly seeded database
    # WHEN /health is called
    response = client.get("/health")

    # THEN the service reports itself ready with every product
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["products"] == 100


def test_sale_rate_reduces_the_price() -> None:
    # GIVEN product_045 costs 55.00
    # WHEN a 25% sale is applied
    response = client.post("/price", json={"product": "product_045", "sale_rate": 25})

    # THEN the final price is 41.25
    assert response.status_code == 200
    body = response.json()
    assert body["product"] == "product_045"
    assert body["base_price"] == 55.0
    assert body["final_price"] == 41.25


def test_zero_sale_rate_keeps_the_base_price() -> None:
    # GIVEN product_000 costs 10.00
    # WHEN the sale rate is 0
    response = client.post("/price", json={"product": "product_000", "sale_rate": 0})

    # THEN the final price equals the base price
    assert response.status_code == 200
    assert response.json()["final_price"] == 10.0


def test_unknown_product_is_refused() -> None:
    # GIVEN a product that does not exist
    # WHEN /price is called
    response = client.post("/price", json={"product": "product_999", "sale_rate": 10})

    # THEN the service refuses
    assert response.status_code == 404


def test_each_request_writes_one_log_line() -> None:
    log_path = Path(os.environ["DEMO_LOG"])
    before = len(log_path.read_text(encoding="utf-8").splitlines())

    # GIVEN a priced request
    response = client.post("/price", json={"product": "product_001", "sale_rate": 10})

    # WHEN the request log is read
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()

    # THEN exactly one JSON object was added, holding the request fields
    assert response.status_code == 200
    assert len(lines) == before + 1
    entry = json.loads(lines[-1])
    assert entry["route"] == "POST /price"
    assert entry["product"] == "product_001"
    assert entry["base_price"] == 11.0
    assert entry["final_price"] == 9.9
    assert entry["release"]
