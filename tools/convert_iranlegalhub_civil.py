"""Convert the three publicly available IranLegalHUB Civil Code JSON volumes.

IMPORTANT: Output is UNVERIFIED legal text. It must pass authoritative source review
before legal publication. This tool does not scrape a website or contact the internet.

Usage:
    python tools/convert_iranlegalhub_civil.py /path/to/vol1.json /path/to/vol2.json /path/to/vol3.json -o storage/civil-unverified.json
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

SOURCE = "https://github.com/GeekNeuron/IranLegalHUB/tree/main/laws/civil_code"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("volumes", nargs="+", help="Original JSON volumes downloaded with their attribution")
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()
    docs = []
    articles = []
    for filename in args.volumes:
        data = json.loads(Path(filename).read_text(encoding="utf-8"))
        for section in data["divisions"]:
            for art in section["articles"]:
                articles.append({"number": str(art["article_number"]), "text": art["text"]})
    counts = [int(article["number"]) for article in articles]
    if len(counts) != len(set(counts)):
        raise ValueError("Duplicate article numbers in source")
    missing = sorted(set(range(1, 1336)) - set(counts))
    if missing:
        raise ValueError(f"Missing numbered articles: {missing[:12]} (and possibly more)")
    docs.append({
        "id": "iran-civil-code-unverified",
        "title": "قانون مدنی ایران — نسخه گردآوری‌شده غیررسمی و تأییدنشده",
        "kind": "law_unverified",
        "source_name": "GeekNeuron/IranLegalHUB (third-party, not an official consolidation)",
        "source_url": SOURCE,
        "articles": sorted(articles, key=lambda item: int(item["number"])),
    })
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"dataset_type": "UNVERIFIED_SOURCE", "documents": docs}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Prepared {len(articles)} UNVERIFIED articles for review: {output}")

if __name__ == "__main__":
    main()
