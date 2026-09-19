# Evaluator-only, Tier D. See repro_test.py for provenance.
"""
Independent behavioral check for click's Path(resolve_path=True) symlink
handling -- beyond the single reported scenario (a symlink one level deep
in the same directory as the target).
"""
import os

import click
from click.testing import CliRunner


def _make_path_type_checker():
    @click.command()
    @click.argument("filename", type=click.Path(exists=True, resolve_path=True))
    def touch(filename):
        click.echo(click.format_filename(filename))

    return touch


def test_relative_symlink_in_subdirectory_resolves(tmp_path):
    """A relative symlink pointing into a DIFFERENT subdirectory (not just
    the same directory as in the original report) must still resolve."""
    target_dir = tmp_path / "data"
    target_dir.mkdir()
    target_file = target_dir / "real.txt"
    target_file.write_text("x")

    link_dir = tmp_path / "links"
    link_dir.mkdir()
    link = link_dir / "alias.txt"
    os.symlink(os.path.join("..", "data", "real.txt"), link)

    runner = CliRunner()
    result = runner.invoke(_make_path_type_checker(), [str(link)])
    assert result.exit_code == 0, result.output


def test_absolute_symlink_still_resolves(tmp_path):
    """An absolute-target symlink (not a relative one) must continue to
    work -- the fix must not regress the already-working absolute case."""
    target_file = tmp_path / "real2.txt"
    target_file.write_text("x")
    link = tmp_path / "alias2.txt"
    os.symlink(str(target_file), link)

    runner = CliRunner()
    result = runner.invoke(_make_path_type_checker(), [str(link)])
    assert result.exit_code == 0, result.output


def test_non_symlink_path_is_unaffected(tmp_path):
    """A plain, non-symlinked file must still work exactly as before."""
    plain = tmp_path / "plain.txt"
    plain.write_text("x")

    runner = CliRunner()
    result = runner.invoke(_make_path_type_checker(), [str(plain)])
    assert result.exit_code == 0, result.output
