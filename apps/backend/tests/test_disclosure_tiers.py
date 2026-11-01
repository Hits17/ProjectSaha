"""
Regression suite for SAHA-003 — trade-secret data served to anonymous callers.

`ListingResponse` was used for both the owner view and the public browse
endpoints, so `GET /api/v1/listings/public` returned the creator's private
description, the complete bill of materials (material names, specifications,
quantities, criticality flags) and the filenames of confidential vault documents
— to callers with no credentials at all, through an internet-facing proxy.

For most listed assets the BOM *is* the invention; the PDF in the vault is a
formality. This was the highest-ranked finding in the audit on exploitability ×
business impact, and a 141-test unit suite could not see it, because the defect
was in a response model rather than in any function's behaviour.

The `test_no_confidential_field_reachable_*` tests are the durable ones: they
assert over the *whole* forbidden field set, so a field added to the public model
later fails here rather than shipping.
"""

import pytest

from app.api.schemas.listing import OwnerListingResponse, PublicListingResponse

# Fields whose disclosure would hand over the manufacturing recipe or reveal the
# existence and nature of unfiled filings. None may ever appear in a T0 response.
CONFIDENTIAL_FIELDS = {
    "description",
    "bom_items",
    "vault_assets",
    "equipment_requirements",
    "batch_size_definition",
    "view_count",
}


def test_public_model_declares_no_confidential_field():
    leaked = CONFIDENTIAL_FIELDS & set(PublicListingResponse.model_fields)
    assert not leaked, (
        f"PublicListingResponse is world-readable and must never carry {leaked}. "
        "Add the field to OwnerListingResponse instead."
    )


def test_owner_model_still_carries_everything_the_creator_needs():
    missing = CONFIDENTIAL_FIELDS - set(OwnerListingResponse.model_fields)
    assert not missing, f"OwnerListingResponse lost {missing} — the creator's own view broke"


def test_public_model_keeps_the_teaser_fields():
    """The teaser has to remain useful, or the fix has broken discovery."""
    for field in ("id", "title", "product_category", "tags", "public_description", "status"):
        assert field in PublicListingResponse.model_fields


def test_serialising_a_listing_as_public_drops_confidential_values():
    """Belt and braces: even given an object carrying every field, the public
    model must not emit the confidential ones."""

    class _Fake:
        id = "00000000-0000-0000-0000-000000000001"
        creator_id = "00000000-0000-0000-0000-000000000002"
        title = "Widget"
        product_category = "industrial_manufacturing"
        tags = ["a"]
        public_description = "teaser"
        description = "SECRET private description"
        equipment_requirements = ["SECRET press"]
        batch_size_definition = "SECRET 500u"
        status = "published"
        view_count = 7
        bom_items = []
        vault_assets = []
        created_at = "2026-01-01T00:00:00Z"
        updated_at = "2026-01-01T00:00:00Z"

    dumped = PublicListingResponse.model_validate(_Fake(), from_attributes=True).model_dump()
    assert "SECRET" not in str(dumped)
    assert CONFIDENTIAL_FIELDS.isdisjoint(dumped)


# ── Route-level: the shape actually returned over HTTP ──────────────────────

@pytest.mark.anyio
async def test_public_listing_route_declares_the_public_model(client):
    """The route's response_model is what actually governs the wire format."""
    from app.main import app

    for route in app.routes:
        if getattr(route, "path", None) == "/api/v1/listings/public":
            assert route.response_model is not None
            assert "PublicListingResponse" in str(route.response_model)
            return
    pytest.fail("/api/v1/listings/public route not found")


@pytest.mark.anyio
async def test_public_offset_is_bounded(client):
    """Unbounded `offset` let the entire corpus be walked in one pass."""
    r = await client.get("/api/v1/listings/public", params={"offset": 10_000_000})
    assert r.status_code == 422


@pytest.mark.anyio
async def test_public_limit_is_capped(client):
    r = await client.get("/api/v1/listings/public", params={"limit": 5000})
    assert r.status_code == 422


def test_search_results_use_the_public_model():
    """Search embeds a listing too — the same leak existed there."""
    from app.api.schemas.search import SearchResult

    annotation = str(SearchResult.model_fields["listing"].annotation)
    assert "PublicListingResponse" in annotation, (
        "Search results must carry the teaser tier; they are reachable "
        "unauthenticated via get_optional_user"
    )
