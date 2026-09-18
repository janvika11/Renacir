from textstats import collect_tags


def test_collect_tags_no_accumulation_across_three_calls():
    assert collect_tags("x") == ["x"]
    assert collect_tags("y") == ["y"]
    assert collect_tags("z") == ["z"]
