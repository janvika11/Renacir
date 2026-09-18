from config import get_setting


def test_present_key_is_unaffected():
    assert get_setting({"timeout": "30"}, "timeout") == "30"


def test_missing_key_with_different_key_name():
    assert get_setting({"retries": "3"}, "backoff") == "unset"
