"""Original legal-topic taxonomy and related-document research browsing."""
import copy
import json
import pytest
from legalcore.corpus import import_directory, corpus_browse, corpus_relations, corpus_search, corpus_stats
from legalcore.store import connect
from legalcore.taxonomy import CATEGORIES, category_catalog


@pytest.fixture
def db(tmp_path):
    conn = connect(str(tmp_path / "topics.sqlite3"))
    yield conn
    conn.close()


@pytest.fixture
def sample():
    with open("examples/corpus-demo/sample-batch.json", encoding="utf-8") as f:
        return json.load(f)


def stage(tmp_path, data):
    folder = tmp_path / "sources"
    folder.mkdir(exist_ok=True)
    (folder / "data.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(folder)


def test_category_registry_is_independently_owned():
    assert len(category_catalog()) >= 30
    assert CATEGORIES["civil"] == "حقوق مدنی"
    assert len(CATEGORIES) == len(set(CATEGORIES))


def test_category_filter_and_counts(db, sample, tmp_path):
    assert import_directory(db, stage(tmp_path, sample))["new_snapshots"] == 2
    stats = corpus_stats(db)
    names = {row["slug"]: row["documents"] for row in stats["by_category"]}
    assert names["civil"] == 1
    assert names["judicial_practice"] == 1
    browse = corpus_browse(db, category="civil")
    assert browse["total"] == 1
    assert browse["results"][0]["kind"] == "law"
    assert browse["publicly_published"] is False
    assert corpus_browse(db, kind="regulation")["total"] == 1
    assert corpus_browse(db, category="civil", kind="regulation")["total"] == 0


def test_filtering_search_only_returns_tagged_latest(db, sample, tmp_path):
    import_directory(db, stage(tmp_path, sample))
    assert corpus_search(db, "آزمایشی", category="civil")["total"] >= 1
    assert corpus_search(db, "آزمایشی", category="banking")["total"] == 0
    assert corpus_search(db, "آزمایشی", kind="regulation")["total"] >= 1


def test_topic_revision_is_new_snapshot_and_history_remains(db, sample, tmp_path):
    path = stage(tmp_path, sample)
    import_directory(db, path)
    changed = copy.deepcopy(sample)
    changed["documents"][0]["categories"] = ["tax"]
    import_directory(db, stage(tmp_path, changed))
    assert corpus_stats(db)["snapshots"] == 3
    assert corpus_browse(db, category="civil")["total"] == 0
    assert corpus_browse(db, category="tax")["total"] == 1
    assert db.execute("SELECT COUNT(*) FROM corpus_snapshot_categories").fetchone()[0] == 5


def test_claimed_relations_are_not_asserted_as_verified(db, sample, tmp_path):
    import_directory(db, stage(tmp_path, sample))
    result = corpus_relations(db, "fictional-iran-regulation-001")
    assert len(result["relations"]) == 1
    assert result["relations"][0]["type"] == "implements"
    assert result["relations"][0]["target_present"] is True
    assert result["relations"][0]["verified"] is False


def test_relation_to_missing_target_is_visible_but_not_authoritative(db, sample, tmp_path):
    sample["documents"][1]["relations"][0]["target_id"] = "missing-fictional-doc"
    import_directory(db, stage(tmp_path, sample))
    result = corpus_relations(db, "fictional-iran-regulation-001")
    assert result["relations"][0]["target_present"] is False
    assert result["publicly_published"] is False


@pytest.mark.parametrize("cats", [
    ["not-a-topic"], ["civil", "civil"], "civil",
    [1], ["civil"] * 9,
])
def test_unknown_duplicate_or_malformed_categories_rejected(db, sample, tmp_path, cats):
    sample["documents"][0]["categories"] = cats
    report = import_directory(db, stage(tmp_path, sample))
    assert report["files_ok"] == 0
    assert report["new_snapshots"] == 0
    assert report["errors"]
    assert corpus_stats(db)["instruments"] == 0


def test_category_filters_validate_user_input(db):
    with pytest.raises(ValueError):
        corpus_browse(db, category="wrong")
    with pytest.raises(ValueError):
        corpus_browse(db, kind="wrong")
    with pytest.raises(ValueError):
        corpus_search(db, "آزمایشی", category="wrong")


def test_previous_unlabeled_imports_remain_browsable(db, sample, tmp_path):
    for doc in sample["documents"]:
        doc.pop("categories", None)
    import_directory(db, stage(tmp_path, sample))
    assert corpus_browse(db)["total"] == 2
    assert corpus_browse(db, category="civil")["total"] == 0
