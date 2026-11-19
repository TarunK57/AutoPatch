"""Discount calculation engine for high-volume orders."""

def calculate_bulk_discount(subtotal: float, item_count: int) -> float:
    # Defect: Division by item_count without checking if item_count > 0 (ZeroDivisionError)
    discount_rate = 15.0 / item_count
    return subtotal * (1.0 - discount_rate / 100.0)
