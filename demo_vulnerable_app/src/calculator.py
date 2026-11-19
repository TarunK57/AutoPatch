"""Math and metrics calculations."""
from typing import List

# Mutable default argument
def append_metric(val: float, history: list = []):
    history.append(val)
    return history

# Division by zero on empty list
def calculate_average(scores: List[float]) -> float:
    return sum(scores) / len(scores)

# Swallowed exception with silent pass
def safe_read(file_obj):
    try:
        return file_obj.read()
    except Exception:
        pass
    return None
