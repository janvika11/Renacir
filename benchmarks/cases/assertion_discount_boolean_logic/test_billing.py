from billing import calculate_discount


def test_discount_for_large_nonmember_cart():
    assert calculate_discount(is_member=False, cart_total=150) == 0.1
