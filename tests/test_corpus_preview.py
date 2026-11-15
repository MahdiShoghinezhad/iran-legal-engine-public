"""Offline Persian research preview must never claim official validation."""
import copy
import json
import pytest
from legalcore.corpus import import_directory
from legalcore.corpus_preview import export_corpus_preview
from legalcore.store import connect


@pytest.fixture
def db(tmp_path):
    connection = connect(str(tmp_path / "test_corpus.sqlite3"))
    yield connection
    connection.close()


@pytest.fixture
def sample():
    return json.loads(open("examples/corpus-demo/sample-batch.json", encoding="utf-8").read())


def seed(db, tmp_path, data):
    root = tmp_path / "source"
    root.mkdir(exist_ok=True)
    (root / "batch.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert import_directory(db, str(root))["files_ok"] == 1


def test_exports_local_searchable_html(db, sample, tmp_path):
    seed(db, tmp_path, sample)
    output = tmp_path / "preview.html"
    result = export_corpus_preview(db, str(output))
    assert result["documents"] == 2
    assert result["units"] == 3
    assert result["offline_only"] is True
    assert result["publicly_published"] is False
    html = output.read_text(encoding="utf-8")
    assert "تأییدنشده" in html
    assert "قانون ساختگی نمونه" in html
    assert "حقوق مدنی" in html
    assert "ماده آزمایشی یک" in html
    assert "default-src 'none'" in html
    assert "fetch(" not in html


def test_only_latest_snapshot_is_exported(db, sample, tmp_path):
    seed(db, tmp_path, sample)
    changed = copy.deepcopy(sample)
    changed["documents"][0]["units"][0]["text"] = "متن جدید ویژه بررسی آرشیو"
    seed(db, tmp_path, changed)
    out = tmp_path / "preview.html"
    export_corpus_preview(db, str(out))
    content = out.read_text(encoding="utf-8")
    assert "متن جدید ویژه بررسی آرشیو" in content
    assert "ماده آزمایشی یک" not in content


def test_untrusted_text_does_not_break_out_of_script(db, sample, tmp_path):
    sample["documents"][0]["units"][0]["text"] = "</script><script>alert(1)</script>"
    seed(db, tmp_path, sample)
    out = tmp_path / "preview.html"
    export_corpus_preview(db, str(out))
    content = out.read_text(encoding="utf-8")
    assert "</script><script>alert(1)</script>" not in content
    assert r"\u003c/script\u003e" in content


def test_empty_database_is_honestly_empty(db, tmp_path):
    out = tmp_path / "empty.html"
    result = export_corpus_preview(db, str(out))
    assert result["documents"] == 0
    assert result["units"] == 0
    assert "تأییدنشده" in out.read_text(encoding="utf-8")


def test_export_size_limit(db, sample, tmp_path, monkeypatch):
    import legalcore.corpus_preview as preview
    seed(db, tmp_path, sample)
    monkeypatch.setattr(preview, "MAX_PREVIEW_JSON_BYTES", 10)
    with pytest.raises(ValueError, match="Too much legal text"):
        export_corpus_preview(db, str(tmp_path / "large.html"))
    assert not (tmp_path / "large.html").exists()
