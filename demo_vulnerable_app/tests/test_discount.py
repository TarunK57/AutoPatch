import pytest
from src.discount_calculator import calculate_bulk_discount

def test_valid_bulk_discount():
    result = calculate_bulk_discount(100.0, 5)
    assert result == 97.0
