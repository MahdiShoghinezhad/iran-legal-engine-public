# ⚖️ Iran Legal Engine — auditable legal text versioning (portfolio demo)

**Working repository name, not the final product trademark.** A public technical demonstration toward an independent Iranian LegalTech platform for citizens, legal professionals, and researchers.

> **Status: executable proof of concept — not a production legal service.** The bundled data is entirely fictional. No live official-law connector, authoritative consolidated legislation, legal advice, or AI model is included.

## Why this matters

Legal technology needs more than search. Changes to statutes can have different approval, publication, enforcement and repeal dates. An AI assistant should not silently cite an unreviewed revision. This project demonstrates a **review-first, source-linked, versioned document pipeline**.

### Currently implemented

- Python package with command-line ingestion and explicit reviewer decisions
- SQLite review queue and immutable, numbered article versions
- Persian Unicode normalization for change-detection hashes
- Idempotent repeated ingests, pending status, rejected/approved decisions
- Read-only FastAPI endpoints for reviewed texts and history
- Automated tests and GitHub Actions CI
- Conversion utility for offline, unverified Civil Code JSON data

### Live demo locally (Python 3.11+)

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e '.[test]'
python -m legalcore.cli --db storage/demo.sqlite3 ingest examples/demo-manifest.json
python -m legalcore.cli --db storage/demo.sqlite3 pending
# Review the numbered pending items, then explicitly approve one:
python -m legalcore.cli --db storage/demo.sqlite3 approve 1 --reviewer demo-reviewer
# Run the API against the same DB:
# Linux/macOS: LEGAL_DB=storage/demo.sqlite3 uvicorn legalcore.api:app --reload
# Windows PowerShell:
$env:LEGAL_DB='storage/demo.sqlite3'
uvicorn legalcore.api:app --reload
```

Visit **`http://127.0.0.1:8000/` for the Persian visual dashboard** (real API-backed, demo-only data). Visit `http://127.0.0.1:8000/docs` for OpenAPI and API testing, or try:

- `GET /` (read-only Persian demo dashboard)
- `GET /api/v1/updates/status` (honest connector status)
- `GET /api/v1/documents/{document_id}/articles` (latest reviewed article index)
- `GET /health`
- `GET /api/v1/documents`
- `GET /api/v1/documents/fictional-legal-demo/articles/1`
- `GET /api/v1/documents/fictional-legal-demo/articles/1/history`

Run tests:

```bash
python -m pytest -q
```

## Self-hosted staging readiness

Before deploying alongside an existing Ubuntu server, inspect [`docs/SELF_HOSTED_STAGING.md`](docs/SELF_HOSTED_STAGING.md) and run the read-only [`scripts/server_readiness.sh`](scripts/server_readiness.sh). The software does **not** require an external hosted app to run; official legal-source access is a separate dependency and is not implemented in this demo.

## Documentation

- [Architecture and scope](docs/ARCHITECTURE.md)
- [Automatic update pipeline](docs/UPDATE_PIPELINE.md)
- [Data provenance and licensing](docs/LEGAL_DATA.md)

## Product plan (not implemented here)

Django + PostgreSQL + approved legal-source connectors + temporal amendments + Persian search + citation-aware RAG + subscription SaaS. Commercial application code, production databases and API keys should live outside this public repository.

## Portfolio value

Demonstrates Python backend design, data engineering, review workflows, legal version histories, REST APIs, relational database design, testing and CI. Add real product screenshots and hosted demo only after those features exist.

## Important safety/rights notice

**This repository contains no verified current Iranian law.** Source access, redistribution terms, legal interpretation, regulator requirements and trademark rights must be checked before commercial deployment. Never publish sensitive client cases or production secrets.

## License

The original demonstration code in this repo is MIT-licensed (see [LICENSE](LICENSE)); this does not grant rights to third-party upstream legal data or product trademarks.

---

## فارسی — معرفی پروژه

**موتور نمونه مدیریت نسخه‌های قوانین ایران** یک پروژه عمومی برای نمایش توانایی‌های مهندسی نرم‌افزار است؛ نام تجاری محصول اصلی هنوز انتخاب و ثبت نشده است.

این نمونه به‌صورت عملی تشخیص تغییر، صف بررسی، تأیید صریح نسخه‌ها، تاریخچه مواد و API خواندنی را پیاده‌سازی می‌کند. اطلاعات همراه آن **ساختگی و آموزشی** است. اتصال زنده به منابع رسمی، بانک قوانین معتبر و پاسخ‌گوی هوش مصنوعی هنوز پیاده‌سازی نشده‌اند.

برای کار واقعی، قبل از انتشار اصلاحات باید منبع رسمی، اعتبار نسخه، تاریخ لازم‌الاجرا شدن و حق بازنشر کنترل شود. کد تجاری اصلی و داده‌های خصوصی در مخزن خصوصی جداگانه نگهداری می‌شوند.
