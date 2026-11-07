# Independent Iranian legal corpus — bulk research ingestion (v1)

**Important: this is an offline research ingestion prototype, not a database of all Iranian laws.** The public repo includes only **fictional** sample documents; no official legal connector, verified consolidation, automatic republication or commercial redistribution is implemented.

## Goal

Ingest many legally distinct classes of materials into an **isolated, owner-controlled research database** while retaining immutable source snapshots and provenance. Nothing imported here is made available in the verified-law API or AI assistant.

Supported examples: laws, constitutional instruments, regulations, bylaws, resolutions, circulars, directives, judicial decisions, advisory opinions, and other instruments. Classification is an input claim, not a legal determination.

## Windows PowerShell demo

From `C:\Users\<username>\iran-legal-engine-public`:

```powershell
git pull
python -m pip install -e ".[test]"
python -m pytest -q

# Preview before writing the research database:
python -m legalcore.cli corpus-import examples/corpus-demo --dry-run

# Import in the dedicated research database:
python -m legalcore.cli corpus-import examples/corpus-demo
python -m legalcore.cli corpus-stats
python -m legalcore.cli corpus-search "آزمایشی"
```

Defaults to `storage/legal-corpus-research.sqlite3`, **not** the public application's `storage/demo.sqlite3`. No VPS, Docker or hosted database is required. A production PostgreSQL migration is a later step.

## JSON input format

Each `.json` file contains a `dataset_type` of `LEGAL_RESEARCH_BATCH_V1` and a `documents` array (up to 1,000 per file). See [`examples/corpus-demo/sample-batch.json`](../examples/corpus-demo/sample-batch.json).

Document fields:

- `id`: globally stable, lowercase, namespaced ID, e.g. `source-1403-000012`; never guess or change identifiers just because a title changes.
- `title`, `kind`, `issuing_authority`: **claimed** identity and issuer.
- `source_name`, `source_url`, optionally `source_reference`: observed location and primary identifier of the supplied text; **neither URL nor source label implies authentication**.
- `dates`: optional map of `approval`, `publication`, `effective`, `expiry`, each with `calendar` (`jalali` or `gregorian`) and original `value`. No automatic conversion or calculation of legal effect is performed.
- `relations`: optional `amends`, `repeals`, `implements`, `interprets`, `relates_to` pointers. These are unverified claims, never automatic supersession.
- `review_state`: must be `UNVERIFIED` when present.
- `units`: array of article/paragraph/note/section/ruling components containing unique `key`, `type`, `text` and optional `heading`.

Save **original documents** and source downloads independently when you have lawful access. This importer stores the original submitted JSON and each article's exact text plus SHA-256, but it does not preserve the original PDF or certify signatures. Verify source terms, redistribution rights, publication dates, later amendments and authoritative legal effect separately.

## Storage and safeguards

- Three independent research tables for instrument identity, immutable document snapshots and component units; a fourth records import audit events.
- Each JSON file is validated in full before any part of that file is written. A bad file is logged as failed and does not block other valid files.
- Re-importing identical content is idempotent; a changed document creates a new immutable snapshot while preserving the previous one.
- `--dry-run` evaluates new/duplicate documents without recording new snapshots.
- The importer never writes `documents`, `article_versions`, or `review_queue` used by the approved-law API. It never makes claims of legal validity.
- Explicitly supplied research DB paths cannot equal the public demo DB or `LEGAL_DB`. Never store corpus research bytes in the public Git repository.
- File size up to 25 MiB, max 5,000 JSON files per import, and up to 20,000 units per document. Use repeated batches to grow the dataset.

## Important distinction between sources

Research input may originate from legally permitted official documents (e.g., laws and resolutions) or third-party text archives. **Official provenance must be demonstrated by an auditable original publication and permission to access/reuse it**; the importer does not make that determination. A law, a judicial decision, and an advisory opinion are not legally interchangeable.

## Next milestones

1. Build a source registry and lawful, rate-limited, versioned adapters for official portals, after checking access terms.
2. Build an expert review and evidence attachment workflow, with calendar-aware effective-date and repeal models.
3. Introduce PostgreSQL for scalable production storage and full-text indexing, with self-hosted backup and access controls.
4. Create an authenticated internal research UI (separate from the approved-law public UI).
5. Publish only expert-reviewed text with evidence and explicit validity windows. No automatic promotion from this quarantine.
