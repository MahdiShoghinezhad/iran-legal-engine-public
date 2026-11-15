# Owner-operated legal source registry (offline, candidates only)

This is a **source metadata registry, not a live government portal connector**. No web pages are downloaded, scraped, or scheduled; the program does not assert access permission, redistribution rights, authenticity, validity, or currency of any legal text. Official and private source terms must be reviewed before creating any network adapter.

## Windows PowerShell: next step

Use the same computer and cloned repository as earlier:

```powershell
cd $HOME\iran-legal-engine-public
git pull
python -m pip install -e ".[test]"
python -m pytest -q

# Add three *candidate* source profiles to the isolated corpus DB:
python -m legalcore.cli corpus-source-init
python -m legalcore.cli corpus-source-list
python -m legalcore.cli corpus-source-show qavanin
```

The three initial candidate source URLs are:

- `https://qavanin.ir/` — legislation and regulations portal
- `https://rrk.ir/` — official publication / legal notices
- `https://dotic.ir/` — national legal information portal

All have `access_rights_state=UNASSESSED`, `redistribution_state=UNASSESSED`, `connector_state=NOT_IMPLEMENTED`, and `automatic_fetch_enabled=0`. These metadata labels are not a promise of official APIs or authorized bulk download.

## Owner-defined source profiles

```powershell
python -m legalcore.cli corpus-source-register demo-source --name "آرشیو ساختگی" --url "https://example.invalid/" --role test_fixture
python -m legalcore.cli corpus-source-show demo-source
```

The following read-only illustration links a locally stored **fictional** evidence receipt to its *claimed* source profile. It does not certify authenticity:

```powershell
python -m legalcore.cli corpus-import examples/corpus-demo
New-Item -ItemType Directory -Force storage/source-input | Out-Null
"این فایل آزمایشی است." | Set-Content -Encoding utf8 storage/source-input/example.txt
python -m legalcore.cli corpus-evidence-add fictional-iran-law-001 storage/source-input/example.txt --source-url https://example.invalid/test
python -m legalcore.cli corpus-evidence-list fictional-iran-law-001
# Substitute the resulting evidence_id:
python -m legalcore.cli corpus-source-link-evidence demo-source 1
```

The receipt is associated only when its **claimed URL hostname** agrees with the registered source hostname (ignoring only a leading `www.`). This catches mistakes but is not a security proof. Raw files stay under ignored `storage/source-evidence/` on your computer. Neither raw legal texts nor credentials are committed to public GitHub.

## Independence, legal verification and scaling

- The registry and its audit records reside inside the **separate research SQLite database** `storage/legal-corpus-research.sqlite3`, not the public approved-law API.
- The bootstrap inserts stable candidate metadata only; it makes **zero HTTP requests**.
- No automatic sync or publishing route can be enabled from this module; official access rights and publication dates are unresolved.
- Once authorized source access formats are verified, implement **independent per-source adapters** with rate limits, audit logs, immutable evidence receipts, and change proposals subject to legal review.
- A future migration to owner-operated PostgreSQL can retain source IDs, evidence hashes, review states and timestamps.
- Product owners must review publication/reuse rules and seek qualified legal advice where relevant; public availability of a law does not automatically grant unrestricted bulk harvesting or commercial redistribution of third-party compilations.
