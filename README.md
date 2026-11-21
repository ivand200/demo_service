# demo-service

Small product pricing API.

## Run

```bash
uv sync
uv run uvicorn app:app --port 8001
```

## Endpoints

```text
GET  /health
POST /price   {"product": "product_045", "sale_rate": 25}
```

## Data

100 products. `price = 10.00 + index`, so `product_000` is 10.00 and
`product_045` is 55.00. Stored in `pricing.sqlite`, created on first start.

Each `POST /price` request is logged to `logs/app.jsonl`, one JSON object per
line. `/health` is not logged.

## Tests

```bash
uv run pytest -q
```
