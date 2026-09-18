from reportpkg import generate_report


def test_generate_report_formats_title():
    assert generate_report("  quarterly summary  ") == "Quarterly Summary"
