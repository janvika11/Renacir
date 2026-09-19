# Evaluator-only, Tier D. See repro_test.py for provenance.
from httpie.sessions import Session


def test_update_headers_skips_none_but_keeps_real_values():
    """Differential/behavioral check: update_headers must skip explicitly
    unset (None) header values without crashing, while still correctly
    decoding and applying every header that DOES have a real value -- not
    just the single --download+--session scenario from the original report.
    """
    session = Session('/tmp/httpie-test-session-independent-check')

    session.update_headers({
        'Accept': None,
        'X-Custom-1': b'value-one',
        'X-Custom-2': None,
        'X-Custom-3': b'value-three',
        'User-Agent': b'HTTPie/9.9.9',  # should be skipped (starts with HTTPie/)
    })

    headers = session['headers']
    assert 'Accept' not in headers
    assert 'X-Custom-2' not in headers
    assert headers['X-Custom-1'] == 'value-one'
    assert headers['X-Custom-3'] == 'value-three'
    assert 'User-Agent' not in headers


def test_update_headers_all_none_does_not_crash():
    """Edge case beyond the single reported scenario: every header unset."""
    session = Session('/tmp/httpie-test-session-independent-check-2')
    session.update_headers({'Accept': None, 'X-Foo': None})
    assert session['headers'] == {}
