# Historical provenance: httpie/cli, issue #235, buggy commit
# 8c892edd4fe700a7ca5cc733dcb4817831d253e2, fixed by commit
# 040d981f00c3f6830b2d0db3daf3c64c080e96e3 ("Fixed custom Host"). httpie is
# BSD-3-Clause licensed (Copyright (c) 2012-2016 Jakub Roztocil). The
# historical regression test (tests/test_regressions.py, added BY the fix
# commit) drives this through the full CLI against http://httpbin.org -- a
# real remote network call, not reproducible offline. This test instead
# exercises the exact buggy property (HTTPRequest.headers in
# httpie/models.py) directly via a locally-constructed
# requests.PreparedRequest, which requires no network access at all and
# isolates the actual bug mechanism precisely. See docs/benchmark_schema.md
# for the REAL-CI-C reconstruction-recipe architecture this case uses.
import requests
from httpie.models import HTTPRequest


def test_custom_host_header_not_duplicated():
    prepared = requests.Request(
        method='GET',
        url='http://localhost/cgi-bin/test.cgi',
        headers={'host': 'www.foo.com'},
    ).prepare()

    rendered = HTTPRequest(prepared).headers

    host_lines = [line for line in rendered.split('\r\n') if line.lower().startswith('host:')]
    assert len(host_lines) == 1, f"expected exactly one Host header, got: {host_lines!r}"
    assert host_lines[0].lower() == 'host: www.foo.com'
