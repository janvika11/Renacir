"""CLI-level tests for `python -m renacir diagnose`'s safety guards. None of
these make a network call — the API-call refusal and missing-config paths
are checked before any provider is ever constructed.
"""

import argparse

from renacir.__main__ import cmd_diagnose
from renacir.config import settings


def _args(**overrides):
    kwargs = dict(
        case_id="assertion-average-off-by-one",
        condition="full_context",
        provider="anthropic",
        model=None,
        temperature=0.0,
        max_tokens=512,
        allow_api_call=False,
        json=False,
    )
    kwargs.update(overrides)
    return argparse.Namespace(**kwargs)


def test_refuses_without_allow_api_call_flag(monkeypatch, capsys):
    monkeypatch.setattr(settings, "llm_model", "claude-fake-1")
    monkeypatch.setattr(settings, "anthropic_api_key", "fake-key")

    exit_code = cmd_diagnose(_args(allow_api_call=False))

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "allow-api-call" in captured.err
    assert "fake-key" not in captured.err
    assert "fake-key" not in captured.out


def test_refuses_missing_model(monkeypatch, capsys):
    monkeypatch.setattr(settings, "llm_model", None)

    exit_code = cmd_diagnose(_args(model=None, allow_api_call=True))

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "model" in captured.err.lower()


def test_refuses_missing_api_key_even_with_allow_api_call(monkeypatch, capsys):
    monkeypatch.setattr(settings, "llm_model", "claude-fake-1")
    monkeypatch.setattr(settings, "anthropic_api_key", None)

    exit_code = cmd_diagnose(_args(allow_api_call=True))

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "ANTHROPIC_API_KEY" in captured.err


def test_unknown_case_id_refused_before_any_config_check(monkeypatch, capsys):
    exit_code = cmd_diagnose(_args(case_id="does-not-exist", allow_api_call=True))

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "unknown case id" in captured.err


def test_model_flag_takes_precedence_over_env_but_neither_leaks_a_key(monkeypatch, capsys):
    monkeypatch.setattr(settings, "llm_model", "env-model-should-not-be-used")
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-should-never-print")

    exit_code = cmd_diagnose(_args(model="cli-model-wins", allow_api_call=False))

    assert exit_code == 1  # still refused, no --allow-api-call
    captured = capsys.readouterr()
    assert "sk-should-never-print" not in captured.out
    assert "sk-should-never-print" not in captured.err
