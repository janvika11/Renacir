# Historical provenance: httpie/cli, issue #412, buggy commit
# 8c33e5e3d31d3cd6476c4d9bc963a4c529f883d2, fixed by commit
# 589887939507ff26d36ec74bd2c045819cfa3d56 ("Fixed --download with
# --session"). httpie is BSD-3-Clause licensed (Copyright (c) 2012-2016
# Jakub Roztocil). This is a Renacir-authored, network-free reproduction of
# the reported failure -- the historical regression test
# (tests/test_sessions.py::test_download_in_session, added BY the fix
# commit) drives it through a full CLI invocation against a live httpbin
# server, which is not reproducible in an offline evaluation. See
# docs/benchmark_schema.md for the REAL-CI-C reconstruction-recipe
# architecture this case uses.
from httpie.sessions import Session


def test_update_headers_with_none_value_does_not_crash():
    session = Session('/tmp/httpie-test-session-repro-412')
    session.update_headers({'Accept': None, 'X-Foo': b'bar'})
