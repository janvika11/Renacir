from textstats import collect_tags


def test_collect_tags_is_independent_across_calls():
    first = collect_tags("a")
    second = collect_tags("b")
    assert first == ["a"]
    assert second == ["b"]
