"""Example: python -m legalcore.cli --db storage/demo.sqlite3 ingest examples/demo-manifest.json"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from .store import connect, initialize
from .ingest import load_manifest, ingest_manifest
from .review import pending, decide, show_pending
from .sync import sync_local_manifest
from .corpus import import_directory, corpus_stats, corpus_search
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
    corp_imp = subs.add_parser("corpus-import", help="Import local legal JSON files into a separate unverified corpus")
    corp_imp.add_argument("directory", help="Folder containing one or more legal corpus JSON manifests")
    corp_imp.add_argument("--dry-run", action="store_true")
    corp_stats = subs.add_parser("corpus-stats", help="Show research corpus statistics")
    corp_search = subs.add_parser("corpus-search", help="Search latest unverified research snapshots")
    corp_search.add_argument("phrase")
    corp_search.add_argument("--limit", type=int, default=20)
    for command in (corp_imp, corp_stats, corp_search):
        command.add_argument("--corpus-db", default="storage/legal-corpus-research.sqlite3",
                             help="Dedicated, quarantined research SQLite database path")
    args = parser.parse_args(argv)
    if args.action.startswith("corpus-"):
        research_db = Path(args.corpus_db).resolve()
        protected_paths = {Path(args.db).resolve(),
                           Path(os.getenv("LEGAL_DB", "storage/portfolio.sqlite3")).resolve()}
        if research_db in protected_paths:
            parser.error("Corpus research database must be separate from the approved-law API database")
        with connect(str(research_db)) as db:
            if args.action == "corpus-import":
                result = import_directory(db, args.directory, dry_run=args.dry_run)
            elif args.action == "corpus-stats":
                result = corpus_stats(db)
            else:
                result = corpus_search(db, args.phrase, limit=args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result.get("errors"):
            raise SystemExit(2)
        return
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
