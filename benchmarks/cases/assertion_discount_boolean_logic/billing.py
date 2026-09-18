def calculate_discount(is_member, cart_total):
    if is_member and cart_total >= 100:
        return 0.1
    return 0.0
