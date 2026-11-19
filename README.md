# PharmOs — Pharmacy Operating System

PharmOs is a tenant-aware pharmacy operating system. Each pharmacy registers
its own shop, owner account, medicine catalog, and operational data. The
system replaces manual rate-list updates with:

1. Photograph a purchase bill on your phone.
2. Google Cloud Vision OCR reads every line item, whatever the distributor's
   layout (Hari Krishna Distributor, Rathore Medicos, Verma Bros, Kaiser
   Drugs, Ravi Medical Agencies, etc. all look different — the parser reads
   each bill's own header row instead of a fixed template).
3. A cost-calculation engine converts rate + GST + discount(s) + free
   quantity into the true landed cost per unit/strip.
4. Every extracted item is fuzzy-matched to your existing ~5,000-medicine
   master rate list.
5. **Nothing is saved until you review and confirm on screen** — you can
   edit any field or pick the correct medicine manually first.
6. On confirm, the master rate list (MRP + cost price) updates, every change
   is logged to a full audit trail, and you get a plain summary of exactly
   what changed.
7. A search screen replaces Ctrl+F, and shows a price-history graph per
   medicine.
8. **Duplicate Invoice Detection**: Prevents double-counting inventory and GST by detecting if a bill with the same distributor and invoice number has already been confirmed. Uploading returns a prominent warning banner, and confirming a duplicate returns an HTTP 409 Conflict hard gate.
9. **Smart Reorder Point Engine**: Calculates data-driven low-stock threshold suggestions based on rolling sales history (30-day default zero-filled series), lead time demand, and safety stock ($Z = 1.65$ for 95% service level). The owner can review suggestions and explicitly apply them to update the low-stock thresholds.
10. **PharmOs Pulse — Privacy-Preserving Regional Heatmap**: Aggregates opted-in OTC surveillance counts into regional health signals. A cell is published only when at least 3 pharmacies contribute; otherwise it is suppressed. No shop, customer, bill, medicine, or raw count is ever exposed by the public API.
11. **Sale invoices & snapshot-based accounting**: POS and single-sale flows persist tenant-scoped sale invoices and sale-time pricing/GST/profit snapshots (Decimal, rounded at defined points). Sales/profit lookups use stored snapshots (with legacy fallback) so historical realized values are not distorted by later medicine price changes.
12. **GST report correctness**: Purchase GST reporting uses `invoice_date`-based perioding (undated confirmed bills are excluded from the period and surfaced with warnings), applies CGST/SGST or IGST based on GSTIN state codes when available, and includes additive sale/output GST estimates derived from sale snapshots for the selected period. See `docs/MIGRATION_NOTES.md` for migration chain (through `0031`) and operational notes.

## PharmOs Pulse — privacy by design

> **See the signal. Never the person.**

PharmOs Pulse reads only privacy-safe `(tenant, condition, date, otc_units)` surveillance counts, aggregates them by region and condition over a 7-day window, applies a **k ≥ 3 anonymity rule**, and publishes only signal labels, trends, volume bands, and contributor counts. Snapshot tables deliberately have no `tenant_id` because they are cross-shop aggregates; privacy is enforced by the k-anonymity rule and a sanitized API DTO.

- Backend: `backend/app/services/heatmap_service.py`, `backend/app/routers/heatmap.py`
- Frontend: `frontend/src/pages/RegionalPulse.jsx` (`/regional-pulse`)
- API: `GET /v1/heatmap/regional`, `GET /v1/heatmap/regions/{region_code}`, `POST /v1/heatmap/refresh` (owner only)
- Migration: `backend/alembic/versions/0026_region_heatmap.py`
- Daily refresh: Celery beat task `refresh_regional_health_heatmap`

## Stack
- **Backend**: Python, FastAPI, SQLAlchemy
- **Database**: MySQL
- **OCR**: Google Cloud Vision (document text detection)
- **Frontend**: React (Vite), react-router, recharts

## Project structure
```
backend/
  app/
    main.py                 FastAPI app
    config.py                settings (.env)
    database.py               MySQL engine/session
    models.py                 ORM schema (medicines, bills, bill_items, rate_history, distributors)
    schemas.py                 API request/response models
    routers/
      bills.py                 upload / review / confirm endpoints
      medicines.py              search + rate history
      dashboard.py               summary stats
    services/
      ocr_service.py             Google Vision wrapper
      bill_parser.py              reconstructs rows/columns from OCR word boxes
      cost_calculator.py           GST/discount/free-qty math
      matcher.py                   fuzzy matching to master list
  scripts/
    import_rate_list.py          one-time import of your existing Excel
    schema.sql                     reference SQL DDL
  tests/
    test_cost_calculator.py        validated against your real uploaded bills
  requirements.txt
  .env.example

frontend/
  src/
    pages/
      UploadBill.jsx              photo upload screen
      ReviewBill.jsx                staging/confirmation screen (the heart of the app)
      SearchDashboard.jsx            Ctrl+F replacement + price history chart
      BillHistory.jsx                 all bills by month/distributor
    api/client.js                 fetch wrapper to the backend
  package.json
  vite.config.js
```

## Setup

### 1. MySQL
```sql
CREATE DATABASE pharmos CHARACTER SET utf8mb4;
```
The schema is created by the Alembic command in the Backend setup step.
The legacy `scripts/schema.sql` file is retained as a reference.

### 2. Google Cloud Vision (OCR)
1. Go to console.cloud.google.com, create a project.
2. Enable the "Cloud Vision API".
3. Create a Service Account → "Create key" → JSON. Save it as
   `backend/gcp-vision-key.json`.
4. New Google Cloud accounts get free credit, and Vision has a free monthly
   quota — enough for a college project demo.

### 3. Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate        # venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env            # then edit .env with your MySQL password + key path
alembic upgrade head
python scripts/import_rate_list.py /path/to/your_pharmacy_rate_list.xlsx

# Run the FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
In a separate terminal, start the Celery worker which processes the background OCR extractions:
```bash
cd backend
source venv/bin/activate
celery -A app.celery_app worker --loglevel=info
```
Visit `http://localhost:8000/docs` for interactive API docs (auto-generated
by FastAPI — very useful for your project demo/viva).

### 4. Frontend
```bash
cd frontend
npm install
npm run dev
```
Visit the printed local URL. Because `vite.config.js` sets `host: true`,
you can also open it from your phone's browser at
`http://<your-computer's-LAN-IP>:5173` (same wifi) — that's how you'd photograph
a bill directly from the shop counter.

## Shared clinical reference data

Salt-to-condition mappings and drug-interaction rules are stored in the global
`salt_conditions` and `drug_interactions` database tables. On first startup,
PharmOs idempotently seeds empty tables from the JSON files under
`backend/app/data/`. The files remain as the packaged baseline and fallback.
Pharmacy owners can manage the live catalog through the protected
`/v1/clinical-reference` API; changes invalidate Redis and in-memory caches.
Apply migrations with `alembic upgrade head` before deploying the new version.

## How the cost formula works
```
gross            = rate * qty
after_discount_1 = gross * (1 - discount_pct/100)
after_discount_2 = after_discount_1 * (1 - special_discount_pct/100)   # compounds, doesn't add
net_landed       = after_discount_2 * (1 + gst_pct/100)
cost_per_unit     = net_landed / (qty + free_qty)
```
This was validated against real line items from your uploaded Hari Krishna
Distributor bill (see `tests/test_cost_calculator.py`) — computed amounts
matched the invoice's printed totals exactly.

## Known limitations (good to state honestly in your project report)
- OCR table reconstruction is heuristic (row clustering + header-based
  column mapping), not a fixed template per distributor — it will
  occasionally mis-place a column on a very cluttered or handwritten bill.
  This is exactly why every extraction goes through a human confirmation
  screen before touching the master list.
- Fuzzy matching (RapidFuzz token-sort ratio) handles spacing/abbreviation
  differences well, but very short or generic names may need manual linking.
- The `FUZZY_MATCH_THRESHOLD` in `.env` controls how confident a match must
  be before it's auto-linked — tune it against your own data.
- Duplicate invoice detection relies on resolved distributor ID and normalized invoice number; bills uploaded without an invoice number or distributor cannot be deduplicated until those fields are filled in.
- The Smart Reorder Point Engine safety-stock formula assumes roughly steady demand over the rolling window; it will be less reliable for highly seasonal medicines or sudden one-off bulk orders.
- GST reporting depends on accurate invoice dates and GSTIN data for precise perioding and inter/intra-state splits; undated bills are excluded from period totals and reported as warnings, and sales/output GST estimates are indicative (derived from recorded sale snapshots) rather than a filing-ready return. See `docs/MIGRATION_NOTES.md`.


## Suggested next features (good "future work" section for your report)
- Low-stock alerts once you add a running quantity-in-stock field.
- Per-distributor template caching, so previously-seen layouts parse faster/more reliably.
- Expiry-date tracking and near-expiry alerts (the bills already contain this data — `bill_items.exp_date`).
