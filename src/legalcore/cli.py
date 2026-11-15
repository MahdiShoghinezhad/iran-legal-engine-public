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
from .corpus import import_directory, corpus_stats, corpus_search, corpus_browse, corpus_relations
from .evidence import attach_evidence, list_evidence, check_evidence, initialize_evidence
from .source_inbox import import_inbox, inbox_history, inbox_diff
from .source_registry import (
    bootstrap_sources, list_sources, get_source,
    register_source, associate_evidence,
)
from .taxonomy import category_catalog
from .corpus_preview import export_corpus_preview
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
    corp_search.add_argument("--category")
    corp_search.add_argument("--kind")
    corp_browse = subs.add_parser("corpus-browse", help="List latest research documents by topic/type")
    corp_browse.add_argument("--category")
    corp_browse.add_argument("--kind")
    corp_browse.add_argument("--limit", type=int, default=50)
    corp_relations = subs.add_parser("corpus-relations", help="Inspect claimed amendment and related-document links")
    corp_relations.add_argument("instrument_id")
    corp_categories = subs.add_parser("corpus-categories", help="List independent legal topic categories")
    corp_preview = subs.add_parser("corpus-preview", help="Export local offline Persian research browser")
    corp_preview.add_argument("--output", default="storage/legal-corpus-preview.html")
    for command in (corp_imp, corp_stats, corp_search, corp_browse, corp_relations, corp_categories, corp_preview):
        command.add_argument("--corpus-db", default="storage/legal-corpus-research.sqlite3",
                             help="Dedicated, quarantined research SQLite database path")
    evidence_add = subs.add_parser("corpus-evidence-add", help="Preserve original local source bytes for a research snapshot")
    evidence_add.add_argument("instrument_id")
    evidence_add.add_argument("input_file")
    evidence_add.add_argument("--source-url", required=True)
    evidence_add.add_argument("--reference", default="")
    evidence_add.add_argument("--snapshot-id", type=int)
    evidence_list = subs.add_parser("corpus-evidence-list", help="List unverified source evidence")
    evidence_list.add_argument("instrument_id")
    evidence_list.add_argument("--snapshot-id", type=int)
    evidence_check = subs.add_parser("corpus-evidence-check", help="Check byte integrity, not legal authenticity")
    evidence_check.add_argument("evidence_id", type=int)
    for command in (evidence_add, evidence_list, evidence_check):
        command.add_argument("--corpus-db", default="storage/legal-corpus-research.sqlite3")
        command.add_argument("--evidence-root", default="storage/source-evidence")
    source_init = subs.add_parser("corpus-source-init", help="Register candidate official source metadata (no downloads)")
    source_list = subs.add_parser("corpus-source-list", help="List research source registry entries")
    source_show = subs.add_parser("corpus-source-show", help="Inspect a source profile and review state")
    source_show.add_argument("source_id")
    source_register = subs.add_parser("corpus-source-register", help="Register one owner-defined source profile")
    source_register.add_argument("source_id")
    source_register.add_argument("--name", required=True)
    source_register.add_argument("--url", required=True)
    source_register.add_argument("--role", required=True)
    source_link = subs.add_parser("corpus-source-link-evidence", help="Link existing research evidence to a claimed source")
    source_link.add_argument("source_id")
    source_link.add_argument("evidence_id", type=int)
    for command in (source_init, source_list, source_show, source_register, source_link):
        command.add_argument("--corpus-db", default="storage/legal-corpus-research.sqlite3")
    inbox_import = subs.add_parser("corpus-inbox-import", help="Capture local source originals and track byte changes, offline")
    inbox_import.add_argument("manifest", help="Local source inbox manifest JSON")
    inbox_import.add_argument("--dry-run", action="store_true")
    inbox_history_cmd = subs.add_parser("corpus-inbox-history", help="Show immutable source observation history")
    inbox_history_cmd.add_argument("source_id")
    inbox_history_cmd.add_argument("instrument_id")
    inbox_history_cmd.add_argument("source_reference")
    inbox_diff_cmd = subs.add_parser("corpus-inbox-diff", help="Compare most recent different source file bytes")
    inbox_diff_cmd.add_argument("source_id")
    inbox_diff_cmd.add_argument("instrument_id")
    inbox_diff_cmd.add_argument("source_reference")
    for command in (inbox_import, inbox_history_cmd, inbox_diff_cmd):
        command.add_argument("--corpus-db", default="storage/legal-corpus-research.sqlite3")
        command.add_argument("--evidence-root", default="storage/source-evidence")
    args = parser.parse_args(argv)
    if args.action.startswith("corpus-"):
        research_db = Path(args.corpus_db).resolve()
        protected_paths = {Path(args.db).resolve(),
                           Path(os.getenv("LEGAL_DB", "storage/portfolio.sqlite3")).resolve()}
        if research_db in protected_paths:
            parser.error("Corpus research database must be separate from the approved-law API database")
        with connect(str(research_db)) as db:
            if args.action == "corpus-inbox-import":
                result = import_inbox(db, args.manifest, dry_run=args.dry_run,
                                      evidence_root=args.evidence_root)
            elif args.action == "corpus-inbox-history":
                result = inbox_history(db, args.source_id, args.instrument_id, args.source_reference)
            elif args.action == "corpus-inbox-diff":
                result = inbox_diff(db, args.source_id, args.instrument_id, args.source_reference,
                                     evidence_root=args.evidence_root)
            elif args.action == "corpus-source-init":
                result = bootstrap_sources(db)
            elif args.action == "corpus-source-list":
                result = list_sources(db)
            elif args.action == "corpus-source-show":
                result = get_source(db, args.source_id)
            elif args.action == "corpus-source-register":
                result = register_source(db, args.source_id, args.name, args.url, args.role)
            elif args.action == "corpus-source-link-evidence":
                initialize_evidence(db)
                result = associate_evidence(db, args.source_id, args.evidence_id)
            elif args.action == "corpus-evidence-add":
                result = attach_evidence(db, args.instrument_id, args.input_file, args.source_url,
                                         source_reference=args.reference, snapshot_id=args.snapshot_id,
                                         evidence_root=args.evidence_root)
            elif args.action == "corpus-evidence-list":
                result = list_evidence(db, args.instrument_id, snapshot_id=args.snapshot_id)
            elif args.action == "corpus-evidence-check":
                result = check_evidence(db, args.evidence_id, evidence_root=args.evidence_root)
            elif args.action == "corpus-import":
                result = import_directory(db, args.directory, dry_run=args.dry_run)
            elif args.action == "corpus-stats":
                result = corpus_stats(db)
            elif args.action == "corpus-search":
                result = corpus_search(db, args.phrase, limit=args.limit,
                                       category=args.category, kind=args.kind)
            elif args.action == "corpus-browse":
                result = corpus_browse(db, category=args.category, kind=args.kind,
                                       limit=args.limit)
            elif args.action == "corpus-relations":
                result = corpus_relations(db, args.instrument_id)
            elif args.action == "corpus-preview":
                result = export_corpus_preview(db, args.output)
            else:
                result = {"categories": category_catalog(), "by_category": corpus_stats(db)["by_category"]}
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
