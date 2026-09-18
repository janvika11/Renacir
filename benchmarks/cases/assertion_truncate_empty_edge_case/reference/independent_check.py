from textstats import truncate_summary


def test_truncate_boundary_sweep():
    assert truncate_summary("hi", 3) == "hi"
    assert truncate_summary("exact", 5) == "exact"
    assert truncate_summary("toolong", 4) == "tool..."
    assert truncate_summary("", 0) == ""
