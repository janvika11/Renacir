# Historical provenance: pallets/click, issue #1921, buggy commit
# 76cc18d1f0bd5854f14526e3ccbce631d8344cce, fixed by commit
# 986f322e435fac5e1fb8505d3683c8a224c18b06 ("resolve relative symlinks to
# the containing directory", PR #2006). click is BSD-3-Clause licensed
# (Copyright 2014 Pallets). Adapted from the reproducer in the original
# issue to be self-contained (constructs its own symlink fixture via
# tmp_path rather than depending on files checked into this repository).
# See docs/benchmark_schema.md for the REAL-CI-C reconstruction-recipe
# architecture this case uses.
import os

import click
from click.testing import CliRunner


def test_resolve_path_follows_relative_symlink(tmp_path):
    target = tmp_path / "foo"
    target.write_text("")
    link = tmp_path / "bar"
    os.symlink("foo", link)

    @click.command()
    @click.argument("filename", type=click.Path(exists=True, resolve_path=True))
    def touch(filename):
        click.echo(click.format_filename(filename))

    runner = CliRunner()
    result = runner.invoke(touch, [str(link)])

    assert result.exit_code == 0, (
        f"expected success, got exit_code={result.exit_code}, output={result.output!r}"
    )
