# Automatic legal updates — implementation plan

## Can it be fully automatic?

**Yes for monitoring and detecting candidate changes**, after an authorized stable integration is available. Automated publication is only safe for changes that meet defined rules, provenance, and approval policy. All unresolved or conflicting cases must await qualified legal review.

1. Register authoritative source, permission/license, expected format, and rate limit.
2. Run idempotent scheduled jobs with per-source checkpoint and last-seen ID.
3. Save original immutable source and content SHA-256, official document identifiers and publication dates.
4. Parse the legal structure, normalize Unicode without destroying original source text.
5. Compare per article and classify: new, amended, repealed, re-numbered, correction, duplicate, uncertain.
6. Cross-check official document and legal timeline (approval, notification, publication, effective date).
7. Stage change in review queue. Notify reviewer for ambiguous cases.
8. Approve changes with signed audit metadata and temporal versioning.
9. Rebuild search and RAG indexes; keep prior versions and notify subscribers if configured.
10. Record sync health; retry backoff, failures and abnormal changes; alert when source is stale.

## Suggested cadence

- Monitor daily as a starting point; increase frequency only where warranted and permitted.
- Always distinguish `last_checked_at`, `source_last_updated_at`, `last_verified_at` and `effective_from`.
- Display staleness and outstanding review counts prominently.

## Current demo behavior

`python -m legalcore.cli ingest ...` calculates a fingerprint and stages changes. It does **not** fetch government websites. It does **not** infer a document's legal validity. Before production, implement a reliable, permitted source adapter and long-lived scheduler on the server, not ad-hoc GitHub scraping.

## Possible source categories

- National legislation and regulation portal (qavanin.ir)
- Official Gazette for provenance of published legal instruments (rrk.ir)
- Institutional publications for circulars and executive instruments (dotic.ir, ministry or judicial sites)

Before use, verify current terms of access, any official APIs/agreements, permissible volume and redistribution rights.
