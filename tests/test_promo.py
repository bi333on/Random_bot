"""Тесты промокодов."""
from app.db.models import PromoCode
from app.services.promo import compute_discount, validate_promo


def test_percent_discount():
    promo = PromoCode(code="X", discount_type="percent", discount_value=20)
    price, discount = compute_discount(1000, promo)
    assert price == 800
    assert discount == 200


def test_fixed_discount_capped_at_price():
    promo = PromoCode(code="X", discount_type="fixed", discount_value=1500)
    price, discount = compute_discount(1000, promo)
    assert price == 0
    assert discount == 1000


async def test_validate_promo(session):
    session.add(PromoCode(code="SALE", is_active=True))
    await session.flush()
    promo = await validate_promo(session, " sale ")
    assert promo is not None
    assert await validate_promo(session, "none") is None


async def test_validate_inactive_promo(session):
    session.add(PromoCode(code="OFF", is_active=False))
    await session.flush()
    assert await validate_promo(session, "off") is None
