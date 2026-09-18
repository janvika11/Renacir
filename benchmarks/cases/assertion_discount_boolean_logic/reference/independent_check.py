from billing import calculate_discount


def test_discount_boundary_combinations():
    assert calculate_discount(is_member=True, cart_total=50) == 0.1
    assert calculate_discount(is_member=False, cart_total=99) == 0.0
    assert calculate_discount(is_member=False, cart_total=100) == 0.1
    assert calculate_discount(is_member=True, cart_total=0) == 0.1
