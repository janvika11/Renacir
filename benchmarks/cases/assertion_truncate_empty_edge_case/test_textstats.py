from textstats import truncate_summary


def test_truncate_exact_width_is_unchanged():
    assert truncate_summary("hello", 5) == "hello"
