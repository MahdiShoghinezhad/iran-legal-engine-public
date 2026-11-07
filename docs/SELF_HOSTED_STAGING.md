# Self-hosted staging deployment (planning, not live production)

The independent legal engine is designed to run on infrastructure controlled by the project owner. This document is a **staging runbook**; no production server has been accessed or configured by this repository.

## Before deploying to an existing Ubuntu 24 server

Do not deploy blindly alongside an existing Laravel product. First gather a minimal read-only resource summary:

```bash
git clone https://github.com/MahdiShoghinezhad/iran-legal-engine-public.git
cd iran-legal-engine-public
cat scripts/server_readiness.sh
bash scripts/server_readiness.sh
```

Review the script before running it. It does not require root, install software, fetch from the Internet after cloning, scan service ports or print credentials. Share only the output you are comfortable sharing; redact hostnames or identifying details.

## Isolation design

- Dedicated staging directory and Linux service account; no use of the existing application's storage.
- Separate application process and SQLite volume for the fictional demo. The future production platform should use a separate PostgreSQL database with scoped credentials.
- Bind the demo API to **127.0.0.1:18080** or another confirmed available loopback port. Do not expose an unprotected demo to the Internet.
- If later publishing a public demo, use the owner's existing reverse proxy, dedicated subdomain, HTTPS, rate limits and a read-only public dataset.
- Keep the primary Laravel application, databases, PHP workers and reverse-proxy config unchanged until readiness and rollback are reviewed.
- Store backup copies off-host under the owner's control; periodically verify restoring them. Never commit backups, API keys, real client documents or official source credentials.

## Local test without Docker

The public README has exact Python setup and local API commands. This proof of concept uses *only fictional data*. It does not yet crawl or validate official legislation.

## Updating laws autonomously

Scheduled ingestion will be self-hosted, idempotent and source-specific. No official website connector or license has been validated yet. New or modified legal text must remain in a review queue until validated against authoritative documents. Reports should show timestamps for last check, last successful source fetch and last legal review.

## Next technical milestones

1. Verify staging resource headroom, ports, reverse proxy and backups.
2. Create an isolated staging service; verify health endpoint and visual dashboard.
3. Introduce a locally scheduled fixture-import job and tests for safe change detection.
4. Implement official-source adapters only after documenting allowed access, publication dates, data provenance and redistribution constraints.
5. Transition private commercial code to Django/PostgreSQL while keeping the public repository as an independently runnable portfolio demonstration.
