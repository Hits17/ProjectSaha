"""Open Innovation Library: input validation and route-protection wiring."""

import pytest
from pydantic import ValidationError

from app.api.schemas.open_resource import (
    OPEN_LICENSES,
    OpenResourceCreate,
    OpenResourceUpdate,
)
from app.db.models.open_resource import OpenResourceType


def _valid(**overrides):
    base = {
        "resource_type": "patent",
        "title": "Expired patent: low-cost water filtration membrane",
        "summary": "Gravity-fed ceramic membrane; patent expired 2021, free to practice.",
        "authors": "A. Rahman; L. Ortiz",
        "identifier": "US7614507B2",
        "source_url": "https://patents.google.com/patent/US7614507B2",
        "license": "public_domain",
        "category": "clean_energy",
        "tags": ["Water", " filtration "],
        "published_year": 2009,
    }
    base.update(overrides)
    return base


def test_valid_create():
    r = OpenResourceCreate(**_valid())
    assert r.resource_type is OpenResourceType.PATENT
    assert r.license == "public_domain"


def test_trademark_type_supported():
    """The library also carries genericized/abandoned trademarks."""
    assert OpenResourceType.TRADEMARK.value == "trademark"
    assert {t.value for t in OpenResourceType} == {"patent", "research_paper", "trademark"}


def test_create_trademark_resource():
    r = OpenResourceCreate(**_valid(
        resource_type="trademark",
        title="Aspirin — former Bayer trademark, now generic in the US",
        summary="Ruled a generic term for acetylsalicylic acid in the US after 1921; "
                "the name is free for anyone to use on the product.",
        identifier="USPTO 0116200",
        source_url="https://tsdr.uspto.gov/#caseNumber=71012345&caseType=SERIAL_NO&searchType=statusSearch",
        license="public_domain",
        category="consumer_products",
        tags=["trademark", "generic"],
    ))
    assert r.resource_type is OpenResourceType.TRADEMARK


def test_browse_filter_accepts_trademark_type():
    """The browse/admin-list routes coerce ?resource_type=trademark to the enum."""
    assert OpenResourceType("trademark") is OpenResourceType.TRADEMARK


def test_tags_normalized_lowercase_trimmed():
    r = OpenResourceCreate(**_valid())
    assert r.tags == ["water", "filtration"]


def test_unknown_license_rejected():
    with pytest.raises(ValidationError):
        OpenResourceCreate(**_valid(license="all_rights_reserved"))


def test_all_declared_licenses_accepted():
    for lic in OPEN_LICENSES:
        assert OpenResourceCreate(**_valid(license=lic)).license == lic


def test_unknown_category_rejected():
    with pytest.raises(ValidationError):
        OpenResourceCreate(**_valid(category="astrology"))


def test_category_optional():
    assert OpenResourceCreate(**_valid(category=None)).category is None


def test_non_http_url_rejected():
    with pytest.raises(ValidationError):
        OpenResourceCreate(**_valid(source_url="ftp://example.com/paper.pdf"))


def test_javascript_url_rejected():
    with pytest.raises(ValidationError):
        OpenResourceCreate(**_valid(source_url="javascript:alert(1)//padding-here"))


def test_short_title_rejected():
    with pytest.raises(ValidationError):
        OpenResourceCreate(**_valid(title="abc"))


def test_too_many_tags_rejected():
    with pytest.raises(ValidationError):
        OpenResourceCreate(**_valid(tags=[f"t{i}" for i in range(11)]))


def test_bad_resource_type_rejected():
    with pytest.raises(ValidationError):
        OpenResourceCreate(**_valid(resource_type="rumor"))


def test_published_year_bounds():
    with pytest.raises(ValidationError):
        OpenResourceCreate(**_valid(published_year=1500))


def test_update_is_partial():
    upd = OpenResourceUpdate(title="A better, clearer resource title")
    assert upd.model_dump(exclude_unset=True) == {"title": "A better, clearer resource title"}


def test_update_can_archive():
    upd = OpenResourceUpdate(is_active=False)
    assert upd.model_dump(exclude_unset=True) == {"is_active": False}


def test_update_rejects_bad_license():
    with pytest.raises(ValidationError):
        OpenResourceUpdate(license="proprietary")


# ── Route protection wiring ──────────────────────────────────────────────────

def test_admin_curation_routes_require_admin():
    """Every /admin/open-resources route must depend on require_admin."""
    from app.api.admin import router
    from app.core.security import require_admin

    curation = [r for r in router.routes if "open-resources" in r.path]
    assert len(curation) >= 5  # list, create, update, approve, reject
    for route in curation:
        deps = [d.call for d in route.dependant.dependencies]
        assert require_admin in deps, f"{route.path} is missing require_admin"


def _route_deps(router, path: str, method: str):
    for route in router.routes:
        if route.path == path and method in route.methods:
            return [d.call for d in route.dependant.dependencies]
    raise AssertionError(f"route {method} {path} not found")


def test_browse_routes_require_login_only():
    """Reads need a logged-in user but no KYC/admin gate."""
    from app.api.open_resources import router
    from app.core.security import get_current_user, require_admin, require_collaborator

    for path, method in [
        ("/api/v1/open-resources", "GET"),
        ("/api/v1/open-resources/{resource_id}", "GET"),
        ("/api/v1/open-resources/{resource_id}/builders", "GET"),
    ]:
        deps = _route_deps(router, path, method)
        assert get_current_user in deps
        assert require_admin not in deps
        assert require_collaborator not in deps


def test_write_routes_require_verified_member():
    """Submitting a resource and declaring a build put content/names in public
    view — both must sit behind the verified-KYC gate."""
    from app.api.open_resources import router
    from app.core.security import require_collaborator

    for path, method in [
        ("/api/v1/open-resources/submissions", "POST"),
        ("/api/v1/open-resources/{resource_id}/build", "POST"),
        ("/api/v1/open-resources/{resource_id}/build", "DELETE"),
    ]:
        deps = _route_deps(router, path, method)
        assert require_collaborator in deps, f"{method} {path} is missing require_collaborator"


# ── Build declarations ───────────────────────────────────────────────────────

def test_build_note_length_capped():
    from app.api.schemas.open_resource import BuildRequest

    with pytest.raises(ValidationError):
        BuildRequest(note="x" * 501)
    assert BuildRequest(note=None).note is None


# ── Search → library suggestions (demand-gap cross-link) ────────────────────

def test_suggestion_terms_cleaned():
    from app.services.open_resources import clean_suggestion_terms

    terms = clean_suggestion_terms(
        ["Water", "  filtration ", "ab", None, "water", "membrane", "", "ceramic"]
    )
    assert terms == ["water", "filtration", "membrane", "ceramic"]


def test_suggestion_terms_capped():
    from app.services.open_resources import clean_suggestion_terms

    terms = clean_suggestion_terms([f"term{i}" for i in range(20)])
    assert len(terms) == 6


def test_search_response_defaults_no_suggestions():
    from app.api.schemas.search import ParsedIntent, SearchResponse

    resp = SearchResponse(intent=ParsedIntent(refined_query="q"), results=[], total=0)
    assert resp.open_resource_suggestions == []


# ── Weekly digest ────────────────────────────────────────────────────────────

def test_digest_compose_single():
    from app.tasks.library_digest import compose_digest

    title, body = compose_digest({"clean_energy": 1})
    assert title == "1 new open resource in the library this week"
    assert "Clean Energy (1)" in body


def test_digest_compose_sorted_by_count():
    from app.tasks.library_digest import compose_digest

    title, body = compose_digest({"software_ai": 2, "clean_energy": 5, None: 1})
    assert title.startswith("8 new open resources")
    assert body.index("Clean Energy (5)") < body.index("Software & AI (2)")
    assert "General (1)" in body
