"""Raw materials marketplace: input validation and seller-ownership policy."""

import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.schemas.material import MATERIAL_CATEGORIES, MaterialCreate, MaterialUpdate
from app.db.models.material import MaterialStatus
from app.services.materials import require_seller


def _valid(**overrides):
    base = {
        "title": "Recycled HDPE pellets",
        "description": "Food-grade recycled HDPE, batch-tested.",
        "category": "polymers_plastics",
        "region": "Gujarat",
        "country": "India",
        "unit": "kg",
        "price_per_unit": Decimal("1.85"),
    }
    base.update(overrides)
    return base


def test_valid_material_create():
    m = MaterialCreate(**_valid())
    assert m.currency == "USD"  # default
    assert m.min_order_quantity is None


def test_unknown_category_rejected():
    with pytest.raises(ValidationError):
        MaterialCreate(**_valid(category="unobtanium"))


def test_all_declared_categories_accepted():
    for cat in MATERIAL_CATEGORIES:
        assert MaterialCreate(**_valid(category=cat)).category == cat


@pytest.mark.parametrize("price", [Decimal("0"), Decimal("-5")])
def test_non_positive_price_rejected(price):
    with pytest.raises(ValidationError):
        MaterialCreate(**_valid(price_per_unit=price))


def test_currency_normalized_to_uppercase():
    assert MaterialCreate(**_valid(currency="inr")).currency == "INR"


def test_short_title_rejected():
    with pytest.raises(ValidationError):
        MaterialCreate(**_valid(title="ab"))


def test_negative_lead_time_rejected():
    with pytest.raises(ValidationError):
        MaterialCreate(**_valid(lead_time_days=-1))


def test_update_is_partial():
    upd = MaterialUpdate(price_per_unit=Decimal("2.10"))
    changes = upd.model_dump(exclude_unset=True)
    assert changes == {"price_per_unit": Decimal("2.10")}


def test_update_can_pause_listing():
    upd = MaterialUpdate(status="paused")
    assert upd.status == MaterialStatus.PAUSED


def test_update_rejects_bad_category():
    with pytest.raises(ValidationError):
        MaterialUpdate(category="not-a-category")


def test_require_seller_allows_owner():
    owner = uuid.uuid4()
    material = SimpleNamespace(seller_id=owner)
    require_seller(material, owner)  # must not raise


def test_require_seller_blocks_non_owner():
    material = SimpleNamespace(seller_id=uuid.uuid4())
    with pytest.raises(HTTPException) as exc:
        require_seller(material, uuid.uuid4())
    assert exc.value.status_code == 403
