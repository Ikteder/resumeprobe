from __future__ import annotations

import pytest

from resumeprobe.contracts import Scenario, matrix


def test_reproducible_identity_and_unique_cells():
    cells = matrix(20261009, 3, ("reference", "langgraph"))
    assert len(cells) == 90
    assert len({cell.operation_id for cell in cells}) == 90
    assert [cell.payload for cell in cells] == [
        cell.payload for cell in matrix(20261009, 3, ("reference", "langgraph"))
    ]


@pytest.mark.parametrize("seed,repetition", [(True, 0), (-1, 0), (1, 50), (1, False)])
def test_invalid_scenario(seed, repetition):
    with pytest.raises(ValueError):
        Scenario("reference", "stable-key", "none", seed, repetition)


def test_empty_and_duplicate_adapters_rejected():
    for adapters in ((), ("reference", "reference")):
        with pytest.raises(ValueError):
            matrix(1, 1, adapters)
