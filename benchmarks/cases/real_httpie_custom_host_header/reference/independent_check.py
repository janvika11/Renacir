# Evaluator-only, Tier D. See repro_test.py for provenance.
import requests
from httpie.models import HTTPRequest


def _host_lines(url, headers):
    prepared = requests.Request(method='GET', url=url, headers=headers).prepare()
    rendered = HTTPRequest(prepared).headers
    return [line for line in rendered.split('\r\n') if line.lower().startswith('host:')]


def test_custom_host_various_casings_not_duplicated():
    """Beyond the single reported lowercase 'host' case: any casing of the
    Host header name supplied by the user must produce exactly one Host
    line, not two."""
    for casing in ('host', 'Host', 'HOST', 'HoSt'):
        lines = _host_lines(
            'http://localhost/cgi-bin/test.cgi', {casing: 'www.foo.com'}
        )
        assert len(lines) == 1, f"casing={casing!r} produced {lines!r}"


def test_host_still_auto_added_when_absent():
    """Regression guard: the fix must not break the original behavior of
    auto-deriving Host from the URL when the user supplies no Host header
    at all."""
    lines = _host_lines('http://example.com/path', {})
    assert len(lines) == 1
    assert lines[0].lower() == 'host: example.com'


def test_custom_host_preserved_with_other_headers_present():
    """A custom Host header must survive even when other unrelated headers
    are also present, not just in the minimal single-header case."""
    lines = _host_lines(
        'http://localhost/x',
        {'host': 'override.example', 'X-Custom': 'abc', 'Accept': '*/*'},
    )
    assert len(lines) == 1
    assert lines[0].lower() == 'host: override.example'
