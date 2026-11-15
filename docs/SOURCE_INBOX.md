# Owner-controlled source intake: offline original-document inbox

This independently implemented workflow accepts **locally obtained source files** and records each observation against an existing unverified research instrument. It makes no web requests, stores immutable original evidence bytes, checks the claimed URL host against the source registry, and flags changed bytes for specialist review. **A changed file is not necessarily an enacted amendment.** Source provenance, legal effect, source permissions and redistribution rights remain **unverified**.

## Try it on Windows, without VPS or any external API

Use the existing repository clone. Start with the fictional example; no official laws or proprietary third-party data are included:

```powershell
cd $HOME\iran-legal-engine-public
git pull
python -m pip install -e ".[test]"
python -m pytest -q

# Create sample research instruments and one source registration:
python -m legalcore.cli corpus-import examples/corpus-demo
python -m legalcore.cli corpus-source-register demo-source --name "منبع ساختگی" --url "https://example.invalid/" --role test_fixture

# Preview what would be imported (no evidence files copied):
python -m legalcore.cli corpus-inbox-import examples/source-inbox-demo/inbox.json --dry-run

# Capture the original fictional text as an immutable local evidence receipt:
python -m legalcore.cli corpus-inbox-import examples/source-inbox-demo/inbox.json

# Inspect the tracked observation and any source-byte differences:
python -m legalcore.cli corpus-inbox-history demo-source fictional-iran-law-001 TEST-001
python -m legalcore.cli corpus-inbox-diff demo-source fictional-iran-law-001 TEST-001
```

The first run reports `FIRST_SEEN`. Repeat the same command to get `UNCHANGED`. Edit `examples/source-inbox-demo/demo-original.txt` *locally* to create a new fictional version, import again, and inspect `CHANGED_BYTES` and its local text diff. Restore or discard that local example edit before committing unrelated changes.

**Note:** The custom source registration is needed only once; a second `corpus-source-register` call for the same ID will report a duplicate. There is no need to share personal credentials or the source file contents with anyone.

## Inbox manifest v1

The `inbox.json` in the example folder contains:

- `dataset_type`: exactly `LEGAL_SOURCE_INBOX_V1`;
- `records`: up to 500 entries;
- per record: a registered `source_id`, existing research `instrument_id`, stable `source_reference`, **relative** `local_file`, and claimed HTTPS `observed_url`;
- optional positive `snapshot_id`, to pin evidence to an earlier immutable document snapshot rather than the latest.

The importer ensures local paths cannot escape the inbox and rejects symlinks, unsupported original formats, invalid source hostnames and duplicate document references in a single manifest. The originals remain under ignored `storage/source-evidence/` by default; their receipts and audit observations live in the distinct **research** SQLite database. It never writes to the public approved-law API or triggers legal publication.

## Safe extension toward official feeds

`qavanin.ir`, `rrk.ir`, and `dotic.ir` are seeded as **candidate source profiles**, not pre-authorized API integrations. A future source-specific adapter should first document the permitted access route, robots/terms, redistribution rights, publication identifiers and acceptable rate, then save immutable original source bytes into an inbox. Where permission or a stable interface is missing, the owner may instead acquire allowed copies manually and feed them to this local workflow.

Do **not** use CAPTCHA bypass, credential copying, proprietary competitor databases or undocumented high-volume scraping to populate the archive. Link original publication details and dates to expert review before treating any material as current law. No scheduler or external website access is enabled by this feature.

## Production hardening still required

This command is a development prototype. Batch preflight precedes file copying, but a disk crash midway can leave already-captured evidence; re-running is idempotent for source bytes while recording a new observation. Use restricted filesystem permissions, encrypted backups and a dedicated operator account. Production needs transactions/outbox recovery, evidence malware screening, legal-review user authentication, signed decisions, page/metadata parser validation and PostgreSQL indexing.
