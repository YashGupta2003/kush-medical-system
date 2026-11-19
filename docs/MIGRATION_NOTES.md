# Migration Notes (fix/multi-tenant-pos-gst-hardening)

This document summarizes migrations introduced on branch `fix/multi-tenant-pos-gst-hardening` (Issues 1–6), operational considerations, and verification status.

## Chain (in order)
- `0027` (pre-existing head on branch context) -> `0028_tenant_scoped_uniques.py` (Issue 1)
- `0028` -> `0029_stock_integrity_constraints.py` (Issue 3)
- `0029` -> `0030_bill_confirm_hardening.py` (Issue 4)
- `0030` -> `0031_sale_invoices_and_snapshots.py` (Issue 5)
- **Issue 6:** no schema migration required; changes are service/router/schema/test-level (GST report correctness and cache invalidation).

Current Alembic head after Issue 5: **`0031`**.

## 0028 — Tenant-scoped business-key uniqueness (Issue 1)
- **Intent:** enforce tenant-scoped composite uniques for `users.username`, `distributors.name`, `medicines.barcode`, `customers.phone`, `cold_chain_units.unit_label` while keeping global/system/reference uniques global.
- **Defensive/idempotent:** checks table/index/unique presence before create/drop where possible; supports SQLite and MySQL patterns used in this codebase.
- **Risk:** pre-existing cross-tenant/global duplicates in legacy data can conflict during unique creation on some engines/data states (validate before production upgrade).

## 0029 — Stock integrity constraints (Issue 3)
- **Intent:** add DB-level guardrail `CHECK (medicines.current_stock >= 0)` (`ck_medicines_current_stock_non_negative`) to prevent negative inventory at the database layer.
- **Defensive/idempotent:** dialect-aware handling; SQLite batch-alter patterns where needed.
- **Risk/requirement:** upgrade will fail if existing rows already violate `current_stock >= 0` (must remediate data first). MySQL-specific constraint/locking behavior should be validated in staging.

## 0030 — Bill confirmation hardening (Issue 4)
- **Intent:** add `bills.confirmed_invoice_key` (nullable) with unique constraint/index `uq_bills_confirmed_invoice_key` to prevent duplicate confirmed invoices at DB level; backfill keys for existing confirmed bills where dedup-able.
- **Defensive/idempotent:** inspects existing columns/indexes/uniques; MySQL/SQLite-safe creation paths.
- **Important behavior:** migration **aborts upgrade** if existing duplicate confirmed invoices are detected (so they can be resolved intentionally). `confirmed_invoice_key` remains nullable when not dedup-able (e.g. missing distributor/invoice context) to preserve intent without breaking legacy rows.

## 0031 — Sale invoices and sale-time snapshots (Issue 5)
- **Intent:** introduce tenant-scoped sale invoice headers and counters (`sale_invoices`, `sale_invoice_counters`) and persist per-sale-line pricing/GST/profit snapshots on `sales` captured at sale time (Decimal-based money/quantity snapshot columns).
- **Defensive/idempotent:** creates tables/columns/indexes only when missing; backfills legacy `sales` rows into legacy invoice records and populates snapshot fields best-effort from available legacy/current data; seeds per-tenant counters from existing non-legacy invoice numbers.
- **Notes:** unique/index guards created in MySQL/SQLite-safe forms where practical. Legacy backfill is best-effort and cannot reconstruct historical invoice/tax context not present in prior data (new sales persist authoritative snapshots).

## Issue 6 (no migration)
- **Intent:** correct GST reporting math/perioding/splits and cache invalidation without schema changes.
- **Behavior:** purchase GST period is based on `Bill.invoice_date`; confirmed bills without `invoice_date` are excluded from the selected period and reported via warnings/counts/ids (not silently bucketed). CGST/SGST vs IGST derived from GSTIN state codes when available (falls back to intra-state with warning). Sales/output GST estimates are additive and snapshot-based for the period. `invalidate_analytics_cache()` now clears analytics/GST/profit cache namespaces (`kush_cache:` and `analytics:`).

## Operational guidance
- **Run migrations in order:** `alembic upgrade head` from the app’s configured DB. Validate on a staging copy with production-like data first (especially `0029` non-negative stock and `0030` duplicate-confirmed-invoice abort/backfill).
- **Idempotency:** migrations are written to be defensive, but always take a backup/snapshot before upgrade and verify row counts/constraints after.
- **Concurrency/locking:** row-locking paths (`SELECT ... FOR UPDATE`) are exercised by code on supported dialects; **MySQL-specific lock behavior is not fully verifiable on local SQLite**.
- **Money/precision:** new/changed sale snapshot and GST calculations use `Decimal` with `ROUND_HALF_UP` to 2 decimal places at defined points.
- **Tenant isolation:** application-level tenant filtering/isolation semantics remain unchanged; migrations add integrity/uniqueness guards consistent with tenant scoping.

## Verification status (local)
- **Backend tests:** `464 passed, 1 skipped, 21 warnings` (full suite, `PYTHONPATH=backend backend/venv/bin/python -m pytest -q`) on local environment after Issues 5–6. Earlier baseline on this branch reported `453 passed, 1 failed, 1 skipped` with the sole failure `tests/test_rate_limits.py::test_copilot_rate_limit` due to unavailable external Groq model `llama-3.3-70b-versatile` (environment/unrelated); that failure was not observed in the final local run.
- **Frontend:** `npm run build` passed; `npm test -- --run` passed (**20 tests**, 4 files).
- **Unverified/manual:** MySQL-specific migration/runtime behavior (locking, constraint enforcement nuances, large-table DDL/backfill performance), production-data duplicate/integrity prechecks for `0029/0030`, and end-to-end CA-facing GST filing validation against real invoices/inter-state cases.
