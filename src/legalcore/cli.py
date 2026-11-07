"""Example: python -m legalcore.cli --db storage/demo.sqlite3 ingest examples/demo-manifest.json"""
from __future__ import annotations
import argparse
import json
from .store import connect, initialize
from .ingest import load_manifest, ingest_manifest
from .review import pending, decide, show_pending
from .sync import sync_local_manifest
from .research import (
    import_civil_research, research_stats, research_article,
    research_search, export_research_preview,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Iran Legal Engine demo workflow")
    parser.add_argument("--db", default="storage/demo.sqlite3", help="SQLite database path")
    subs = parser.add_subparsers(dest="action", required=True)
    subs.add_parser("init")
    ingest = subs.add_parser("ingest")
    ingest.add_argument("manifest")
    ingest.add_argument("--dry-run", action="store_true")
    subs.add_parser("pending")
    research_import = subs.add_parser("research-import-civil")
    research_import.add_argument("volumes", nargs=3, help="Three locally saved volumes, in order")
    subs.add_parser("research-stats")
    research_lookup = subs.add_parser("research-article")
    research_lookup.add_argument("number", type=int)
    research_lookup.add_argument("--snapshot-id", type=int)
    research_query = subs.add_parser("research-search")
    research_query.add_argument("phrase")
    research_query.add_argument("--limit", type=int, default=20)
    research_export = subs.add_parser("research-export-preview")
    research_export.add_argument("--output", default="storage/civil-research-preview.html")
    detail = subs.add_parser("show-pending")
    detail.add_argument("review_id", type=int)
    sync = subs.add_parser("sync-local")
    sync.add_argument("manifest")
    sync.add_argument("--dry-run", action="store_true")
    approve = subs.add_parser("approve")
    approve.add_argument("review_id", type=int)
    approve.add_argument("--reviewer", required=True)
    reject = subs.add_parser("reject")
    reject.add_argument("review_id", type=int)
    reject.add_argument("--reviewer", required=True)
    args = parser.parse_args(argv)
    with connect(args.db) as db:
        initialize(db)
        if args.action == "init":
            result = {"initialized": True, "db": args.db}
        elif args.action == "ingest":
            result = ingest_manifest(db, load_manifest(args.manifest), dry_run=args.dry_run)
        elif args.action == "pending":
            result = {"pending": pending(db)}
        elif args.action == "research-import-civil":
            result = import_civil_research(db, args.volumes)
        elif args.action == "research-stats":
            result = research_stats(db)
        elif args.action == "research-article":
            result = research_article(db, args.number, snapshot_id=args.snapshot_id)
        elif args.action == "research-search":
            result = research_search(db, args.phrase, limit=args.limit)
        elif args.action == "research-export-preview":
            result = export_research_preview(db, args.output)
        elif args.action == "show-pending":
            result = show_pending(db, args.review_id)
        elif args.action == "sync-local":
            result = sync_local_manifest(db, args.manifest, dry_run=args.dry_run)
        else:
            result = decide(db, args.review_id, args.reviewer, approve=(args.action == "approve"))
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
