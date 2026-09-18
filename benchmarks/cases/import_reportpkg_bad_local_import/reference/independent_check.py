from reportpkg import helpers
from reportpkg.core import generate_report


def test_generate_report_delegates_to_real_helpers():
    assert generate_report("  test title  ") == helpers.format_title("  test title  ")


def test_generate_report_handles_multiple_calls():
    assert generate_report("first") == "First"
    assert generate_report("second") == "Second"
