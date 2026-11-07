# Architecture — portfolio demo versus commercial system

```text
[Authorized official sources: future adapters]
                    |
                    v
     [Download / provenance / checksum]
                    |
                    v
       [Validate + normalize + diff]
                    |
                    v
            [Review queue]
                    |
          [Human/legal review]
                    |
                    v
         [Immutable version history]
                    |
                    v
           [Read-only REST API]
                    |
      [Search + AI/RAG: future work]
```

## Implemented in this public repository

- Python package with a runnable CLI and read-only FastAPI endpoints
- SQLite document index and a review queue
- Normalized fingerprint-based change detection (Arabic/Persian glyph normalization)
- Explicit human approval/rejection before a version is published
- Approved article history and basic automated tests
- A converter for third-party civil code JSON volumes (outputs **unverified** text)
- GitHub Actions CI on pushes and pull requests

## Not implemented — do not claim these features in portfolio descriptions

- No licensed or official live data connector
- No automatic legal validation, official consolidation, or authoritative corpus
- No full-text search, user accounts, production authorization, subscriptions or payments
- No AI/RAG, no online hosting, no production incident response
- No scheduled production ingestion or alert delivery

## Planned commercial architecture

- Django / Django REST Framework for SaaS account and RBAC boundaries
- PostgreSQL with legal document, document relationship and temporal version tables
- Celery (or equivalent durable job queue) and a scheduler for source checks
- Pluggable authorized collectors with rate limits and extraction provenance
- Search index tuned for Persian legal text; citation-aware RAG uses **approved** data
- Object storage for original source documents, checksums and audit trails
- Security: SSO/MFA, tenant isolation, strict admin approval, no exposed secrets

## Data model principles

- Differentiate laws, regulations, rulings, circulars and legal opinions
- Keep approving authority, source publication, entry into force, and repeal separately
- Preserve past text and amendments; do not overwrite legal history
- Mark ambiguous legal validity as `pending_review`, not `in_force`
- All AI answers must cite specific approved versions and temporal context

## Security and ethics

Never put case records, clients' names, credentials, protected documents or sensitive prompts in a public repository. Do not rely on unapproved third-party legal data for consequential advice. Verify source terms, access rules, legal redistribution, and official status before a real connector is deployed.
