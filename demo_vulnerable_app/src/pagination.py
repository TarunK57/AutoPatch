"""Pagination helper."""
from typing import List, Any

def get_page_items(items: List[Any], page: int, page_size: int) -> List[Any]:
    start = (page - 1) * page_size
    # Defect: range lookup beyond bounds
    return items[start:start + page_size]
