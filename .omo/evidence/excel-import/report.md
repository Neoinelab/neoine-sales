# Excel contract importer evidence

Owned paths: `excel-upload/{contract_workbook,contract_plan,contract_store,import_contracts}.py`,
`excel-upload/README.md`, `backend/tests/unit/tools/`.

Implemented: fixed 10-column XLSX reader with Excel dates and row errors, unchanged source workbook,
`유지보수-<고객사명>-<제품명>` names, null Users/amount, vendor/customer/partner reuse,
owner resolution and exact-contract repeat skipping/conflict rejection, transaction-wide insertion,
read-only dry run, backend/.env via app.config with no printed credentials.

Scenarios and observations:

- Before implementation: `cd backend && uv run pytest tests/unit/tools/test_contract_workbook.py --no-cov -q`
  failed collection with missing production module. Captured in `red.txt`.
- Parser/plan suite: `cd backend && uv run pytest tests/unit/tools --no-cov -q`: 13 passed.
  Includes dates/space preservation/Note/empty inspection, reverse dates, unknown cycles,
  existing owner resolution, missing/ambiguous owners, new/exact/conflicting/multiple contract matches.
  Captured in `tests.txt`.
- Type check: `cd backend && uv run mypy ../excel-upload --follow-imports=silent`: success on 4 files.
  Captured in `mypy.txt`.
- CLI help: `cd backend && uv run python ../excel-upload/import_contracts.py --help`: exit 0,
  filename and `--dry-run` shown. Captured in `help.txt`.
- Current configured DB read-only CLI: `cd backend && uv run python ../excel-upload/import_contracts.py contracts_20261123.xlsx --dry-run`:
  exit 1, `2행: 영업담당 '박계형(Neo Park)' 일치 사용자 0명`. Captured in `dry-run.txt`.
  This is expected validation against the current DB, not a successful import.
- Actual workbook parsing through `read_workbook`: 42 rows, all Deal names have 유지보수 prefix.
  Captured in `workbook.txt`.
- Lint/format verification captured in `lint.txt`.

No DB write run was performed. Actual write/rollback against PostgreSQL remains unverified;
the import requires the associated schema migration and real matching sales/admin users first.
No browser was launched. No dependencies added. Source ownership is separated into workbook boundary,
pure identity/idempotency rules, SQL transaction adapter, and CLI/config boundary.
