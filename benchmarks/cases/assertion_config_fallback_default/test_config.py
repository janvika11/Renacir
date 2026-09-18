from config import get_setting


def test_missing_key_returns_sentinel():
    assert get_setting({}, "timeout") == "unset"
