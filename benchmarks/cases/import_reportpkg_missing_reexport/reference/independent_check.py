import reportpkg
import reportpkg.core


def test_reexport_is_same_object_as_core_symbol():
    assert reportpkg.generate_report is reportpkg.core.generate_report


def test_reexported_function_still_works_correctly():
    assert reportpkg.generate_report("  another title  ") == "Another Title"
