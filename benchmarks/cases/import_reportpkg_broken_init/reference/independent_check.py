import reportpkg


def test_package_imports_cleanly():
    assert reportpkg.generate_report is not None


def test_all_declared_exports_still_resolve():
    for name in reportpkg.__all__:
        assert hasattr(reportpkg, name)
