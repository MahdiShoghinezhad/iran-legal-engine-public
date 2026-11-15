"""Registry tests: seeded portals never fetch, license, or certify material."""
import sqlite3
import pytest
from legalcore.source_registry import (
    bootstrap_sources, initialize_source_registry, list_sources,
    register_source, get_source, associate_evidence,
)

@pytest.fixture
def db():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    initialize_source_registry(connection)
    # Minimal pre-existing evidence table required by the foreign-key link.
    connection.execute(
        "CREATE TABLE corpus_source_evidence (id INTEGER PRIMARY KEY, "
        "snapshot_id INTEGER NOT NULL, observed_url TEXT NOT NULL, "
        "legal_status TEXT NOT NULL DEFAULT 'UNVERIFIED')"
    )
    yield connection
    connection.close()


def test_default_has_no_auto_fetch(db):
    result=bootstrap_sources(db)
    assert result["candidate_profiles_added"]==3
    assert result["data_collected"] is False
    assert result["permissions_reviewed"] is False
    record=list_sources(db)
    assert record["count"] == 3
    assert record["network_connections_made"] == 0
    assert record["official_api_integrations"] == 0
    assert all(x["automatic_fetch_enabled"] == 0 for x in record["sources"])
    assert all(x["access_rights_state"]=="UNASSESSED" for x in record["sources"])


def test_idempotent_bootstrap(db):
    assert bootstrap_sources(db)["candidate_profiles_added"] == 3
    assert bootstrap_sources(db)["candidate_profiles_added"] == 0


def test_custom_source_and_no_legal_verification(db):
    result=register_source(db,"demo-source","Test Archive","https://example.invalid/", "test_fixture")
    assert result["automatic_fetch_enabled"] == 0
    assert result["legal_authenticity_verified"] is False
    assert get_source(db,"demo-source")["redistribution_state"] == "UNASSESSED"
    with pytest.raises(sqlite3.IntegrityError):
        register_source(db,"demo-source","Duplicate","https://example.invalid/","test_fixture")


@pytest.mark.parametrize("url", [
    "file:///etc/hosts", "http://example.invalid/", "https://user:password@example.invalid/",
    "https://example.invalid:8443", "https://example.invalid/#fragment", "https://",
])
def test_reject_untrusted_or_non_https_source_urls(db,url):
    with pytest.raises(ValueError):
        register_source(db,"demo-source","Test Archive",url,"test_fixture")


def test_evidence_association_is_claim_only(db):
    register_source(db,"demo-source","Test Archive","https://example.invalid/", "test_fixture")
    db.execute("INSERT INTO corpus_source_evidence(id,snapshot_id,observed_url) VALUES(1,10,?)",
               ("https://www.example.invalid/document/1",))
    db.commit()
    rec=associate_evidence(db,"demo-source",1)
    assert rec["legal_validity_verified"] is False
    assert rec["official_identity_verified"] is False
    assert associate_evidence(db,"demo-source",1)==rec
    assert list_sources(db)["sources"][0]["linked_evidence"]==1


def test_reject_mismatched_host_and_missing_receipt(db):
    register_source(db,"demo-source","Test Archive","https://example.invalid/", "test_fixture")
    with pytest.raises(ValueError,match="does not exist"):
        associate_evidence(db,"demo-source",999)
    db.execute("INSERT INTO corpus_source_evidence(id,snapshot_id,observed_url) VALUES(1,10,?)",
               ("https://example.invalid.evil.test/doc",))
    with pytest.raises(ValueError,match="hostname"):
        associate_evidence(db,"demo-source",1)


def test_never_allow_fetch_in_database(db):
    bootstrap_sources(db)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE legal_source_registry SET automatic_fetch_enabled=1 WHERE id='qavanin'")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE legal_source_registry SET access_rights_state='ALLOWED' WHERE id='qavanin'")
