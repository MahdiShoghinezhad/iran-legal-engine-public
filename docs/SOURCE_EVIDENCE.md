# Offline legal source evidence vault (self-hosted prototype)

Each original document supplied by the operator is copied to a local SHA-256 content-addressed vault and linked to one immutable snapshot in the *quarantined* research corpus. This is **not** proof of official origin, legal validity or redistribution rights. Nothing is downloaded from a remote website, and nothing is published to the public approved-law API.

## Windows PowerShell example

```powershell
cd $HOME\iran-legal-engine-public
git pull
python -m pip install -e ".[test]"
python -m pytest -q
python -m legalcore.cli corpus-import examples/corpus-demo
New-Item -ItemType Directory -Force storage/source-input | Out-Null
"این سند فقط برای آزمون و ساختگی است." | Set-Content -Encoding utf8 storage/source-input/test.txt
python -m legalcore.cli corpus-evidence-add fictional-iran-law-001 storage/source-input/test.txt --source-url https://example.invalid/fictional-law-001 --reference FICTIONAL-001
python -m legalcore.cli corpus-evidence-list fictional-iran-law-001
python -m legalcore.cli corpus-evidence-check 1
```

`corpus-evidence-check` reports `file_integrity: ok` when the locally preserved bytes match the original SHA-256. A matching hash says nothing about authenticity of the source or whether its content is current law.

## Boundaries

- Research DB: `storage/legal-corpus-research.sqlite3`; vault: `storage/source-evidence/`; both ignored by Git.
- PDF, HTML, XML, JSON and UTF-8 text originals are accepted (up to 25 MiB each).
- Files are never copied from an unrelated proprietary legal app. Only operator-supplied files from sources they are entitled to access should be imported.
- The UI and API for approved laws remain separate. The evidence tool is an offline CLI, not a public upload endpoint.
- Future official-source adapters will need authorized access, source-specific publishing identifiers, documentary evidence, revision dates, rate limits, and a legal review policy.
- Do not publish source files or research-database backups to GitHub. Keep original evidence in an access-controlled location under the owner's control.

## Benchmark reference — Didban8

The well-established DIDBAN8 application provides a useful functional benchmark: categorized legislation, related precedent and advisory opinions, legal calculators, annotations and search. Our product will implement its own architecture, design, legally obtained corpus and traceable sourcing; do not copy its UI, software, APK or proprietary database.

Reviewed 2026-11-15: https://didban8.ir/ and https://didban8.ir/app/.
