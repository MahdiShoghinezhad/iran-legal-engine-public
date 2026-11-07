# Civil Code — quarantined, offline research workflow

**Status: research only. Not an official consolidated law, legal advice, or a production data pipeline.**

The public repository intentionally contains **no actual Civil Code text**. Our local importer accepts the three JSON volumes from the third-party IranLegalHUB repository. That repository's MIT license is not proof of official legal authenticity, complete amendments, or permission for every downstream commercial data use.

## Quick start on Windows PowerShell

From your local clone (`cd $HOME\iran-legal-engine-public`):

```powershell
# First, fetch the current project code:
git pull
python -m pip install -e ".[test]"

# Download source snapshots once, explicitly. This is NOT live government syncing.
New-Item -ItemType Directory -Force -Path "storage\source-volumes" | Out-Null
$base = "https://raw.githubusercontent.com/GeekNeuron/IranLegalHUB/main/laws/civil_code"
1..3 | ForEach-Object {
    Invoke-WebRequest -Uri "$base/civil_code_vol_$_.json" -OutFile "storage\source-volumes\civil_code_vol_$_.json"
}

# Load only into a SEPARATE research database (never the API's LEGAL_DB):
python -m legalcore.cli --db storage/civil-research.sqlite3 research-import-civil storage/source-volumes/civil_code_vol_1.json storage/source-volumes/civil_code_vol_2.json storage/source-volumes/civil_code_vol_3.json

python -m legalcore.cli --db storage/civil-research.sqlite3 research-stats
python -m legalcore.cli --db storage/civil-research.sqlite3 research-search "معامله"
python -m legalcore.cli --db storage/civil-research.sqlite3 research-article 10

# Generate a searchable HTML research viewer requiring no server or Internet:
python -m legalcore.cli --db storage/civil-research.sqlite3 research-export-preview --output storage/civil-research-preview.html
Start-Process storage/civil-research-preview.html
```

**Important:** do not set `LEGAL_DB` to `storage/civil-research.sqlite3`. The approved-law API must remain separate from this research corpus. Do not upload the generated HTML or raw volume files to the public repository, GitHub Pages, or production web roots.

## Integrity and isolation

- Input must be **exactly three** valid JSON volumes with nonempty article texts and full expected ranges 1–955, 956–1256 and 1257–1335. Missing, duplicate, or out-of-range numbers are rejected.
- SHA-256 fingerprints of the original **bytes** of each file form the immutable snapshot identifier.
- Repeated imports of identical source data are idempotent. Changed sources create a new research snapshot, preserving earlier snapshots.
- Each research article has its original text, original section label and text hash. Unicode normalization applies to search only, never to stored text.
- Research articles live in `civil_research_*` tables and are **never inserted** into `documents`, `article_versions`, or `review_queue`, and have no public API route.
- The offline HTML is generated on the owner's computer, is text-escaped against script injection, and displays a permanent `تأییدنشده` warning.
- The import records source fingerprints and attribution, but cannot prove official text authenticity or correct current legal effect.

## Before a legal-grade release

Obtain official source records with publication and enforcement dates, confirm rights and permitted reuse, compare each material provision with official publications, record amendments/repeals and legal interpretation, and require documented expert review. Only **then** consider placing verified texts in the separate production content database. Never assume that a numeric coverage check makes the texts legally current.
