import pytest
from src.calculator import calculate_average, append_metric

def test_average_valid():
    assert calculate_average([10.0, 20.0, 30.0]) == 20.0

def test_metric_append():
    res = append_metric(5.0, [])
    assert len(res) == 1
