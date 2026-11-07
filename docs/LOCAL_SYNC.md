# Independent local-update prototype (offline-first)

This public demo includes **one-shot local manifest synchronization**. It detects local-file changes, records audit metadata and stages proposed article versions. It does not retrieve Iranian laws or assert submitted documents are authentic. A real official-source connector and legal validation layer are future work.

## Run locally on Windows PowerShell

```powershell
git pull
python -m pip install -e '.[test]'
python -m legalcore.cli --db storage/demo.sqlite3 sync-local examples/demo-manifest.json --dry-run
python -m legalcore.cli --db storage/demo.sqlite3 sync-local examples/demo-manifest.json
python -m legalcore.cli --db storage/demo.sqlite3 pending
python -m legalcore.cli --db storage/demo.sqlite3 show-pending 1
# ONLY after independently checking the entire proposed text and its official provenance:
python -m legalcore.cli --db storage/demo.sqlite3 approve 1 --reviewer local-reviewer
python -m pytest -q
```

To test detection of a revision, copy `examples/demo-manifest.json` to a temporary JSON file, modify a **fictional** article and run `sync-local` again. An edited version stays pending until reviewed. Identical local inputs do not create duplicate pending proposals.

## Later self-hosted scheduling

An owner-controlled scheduler (Windows Task Scheduler or Linux systemd timer) can invoke `sync-local` against a manifest written by a trusted local adapter. Use absolute paths and a dedicated non-privileged service account. **Nothing is scheduled or deployed by this repository**.

The original official-source integration requires access rights, provenance checks, publication and effective dates, and legal review. Automation must not silently delete previous historically applicable legal versions.
