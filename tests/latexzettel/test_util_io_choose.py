"""Characterization tests for latexzettel.util.io.choose_one / choose_many.

Written against the pre-refactor code (C901 request 2026-09-10) to pin the
exact console transcript: prompts, option listing, error messages, retry
loop, return values and the order of validation vs. printing.
"""

from __future__ import annotations

import pytest

from latexzettel.util.io import IO, choose_many, choose_one


class ScriptedIO:
    """Feeds canned answers to ``ask`` and records every prompt and line said."""

    def __init__(self, answers: list[str]) -> None:
        self._answers = iter(answers)
        self.transcript: list[str] = []

    def io(self) -> IO:
        return IO(input_fn=self._ask, print_fn=self._say)

    def _ask(self, prompt: str) -> str:
        self.transcript.append(f"ASK {prompt}")
        return next(self._answers)

    def _say(self, *args, **kwargs) -> None:
        self.transcript.append("SAY " + " ".join(str(a) for a in args))


OPTIONS = ["alpha", "beta", "gamma"]
LISTING = ["SAY Pick:", "SAY   1) alpha", "SAY   2) beta", "SAY   3) gamma"]


# ── choose_one ────────────────────────────────────────────────────────────


def test_choose_one_empty_options_raises_before_output():
    s = ScriptedIO([])
    with pytest.raises(ValueError, match="options no puede ser vacío"):
        choose_one("Pick:", [], io=s.io())
    assert s.transcript == []


@pytest.mark.parametrize("bad", [-1, 3])
def test_choose_one_bad_default_raises_after_listing(bad):
    s = ScriptedIO([])
    with pytest.raises(ValueError, match="default_index fuera de rango"):
        choose_one("Pick:", OPTIONS, default_index=bad, io=s.io())
    assert s.transcript == LISTING


def test_choose_one_valid_number_returns_zero_based():
    s = ScriptedIO([" 2 "])
    assert choose_one("Pick:", OPTIONS, io=s.io()) == 1
    assert s.transcript == LISTING + ["ASK Seleccione un número: "]


def test_choose_one_enter_uses_default():
    s = ScriptedIO([""])
    assert choose_one("Pick:", OPTIONS, default_index=2, io=s.io()) == 2
    assert s.transcript == LISTING + ["ASK Seleccione un número [3]: "]


def test_choose_one_retries_until_valid():
    s = ScriptedIO(["", "x", "0", "4", "3"])
    assert choose_one("Pick:", OPTIONS, io=s.io()) == 2
    ask = "ASK Seleccione un número: "
    assert s.transcript == LISTING + [
        ask, "SAY Entrada inválida. Ingrese un número.",
        ask, "SAY Entrada inválida. Ingrese un número.",
        ask, "SAY Fuera de rango. Ingrese un número entre 1 y 3.",
        ask, "SAY Fuera de rango. Ingrese un número entre 1 y 3.",
        ask,
    ]


def test_choose_one_default_prompt_repeats_on_retry():
    s = ScriptedIO(["9", "1"])
    assert choose_one("Pick:", OPTIONS, default_index=0, io=s.io()) == 0
    ask = "ASK Seleccione un número [1]: "
    assert s.transcript == LISTING + [
        ask, "SAY Fuera de rango. Ingrese un número entre 1 y 3.", ask,
    ]


# ── choose_many ───────────────────────────────────────────────────────────


def test_choose_many_empty_options_raises_before_output():
    s = ScriptedIO([])
    with pytest.raises(ValueError, match="options no puede ser vacío"):
        choose_many("Pick:", [], io=s.io())
    assert s.transcript == []


@pytest.mark.parametrize("bad", [[-1], [0, 3]])
def test_choose_many_bad_default_raises_before_listing(bad):
    s = ScriptedIO([])
    with pytest.raises(ValueError, match="default contiene índices fuera de rango"):
        choose_many("Pick:", OPTIONS, default=bad, io=s.io())
    assert s.transcript == []


def test_choose_many_returns_sorted_unique_zero_based():
    s = ScriptedIO([" 3 , 1,3 "])
    assert choose_many("Pick:", OPTIONS, io=s.io()) == [0, 2]
    assert s.transcript == LISTING + ["ASK Seleccione números separados por coma: "]


def test_choose_many_enter_uses_default_sorted_unique():
    s = ScriptedIO([""])
    assert choose_many("Pick:", OPTIONS, default=[2, 0, 2], io=s.io()) == [0, 2]
    # hint echoes the default as given (order + duplicates), 1-based
    assert s.transcript == LISTING + ["ASK Seleccione números separados por coma [3,1,3]: "]


def test_choose_many_empty_default_list_is_a_default():
    s = ScriptedIO([""])
    assert choose_many("Pick:", OPTIONS, default=[], io=s.io()) == []
    assert s.transcript == LISTING + ["ASK Seleccione números separados por coma []: "]


def test_choose_many_retries_until_valid():
    s = ScriptedIO(["", " , ,", "1,x", "0,2", "2,4", "2"])
    assert choose_many("Pick:", OPTIONS, io=s.io()) == [1]
    ask = "ASK Seleccione números separados por coma: "
    assert s.transcript == LISTING + [
        ask, "SAY Entrada vacía. Intente de nuevo.",
        ask, "SAY Entrada vacía. Intente de nuevo.",
        ask, "SAY Entrada inválida. Use números separados por coma.",
        ask, "SAY Fuera de rango. Use números entre 1 y 3.",
        ask, "SAY Fuera de rango. Use números entre 1 y 3.",
        ask,
    ]
