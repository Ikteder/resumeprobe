from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from resumeprobe.sink import EffectSink


def test_concurrent_stable_key_commits_one_effect(tmp_path):
    sink = EffectSink(tmp_path / "sink.sqlite")
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(
                lambda attempt: sink.apply("op", {"v": 1}, "stable-key", attempt), range(1, 17)
            )
        )
    assert len(sink.snapshot()["effects"]) == 1
    assert all(result == results[0] for result in results)


def test_payload_conflict_does_not_commit_another_effect(tmp_path):
    sink = EffectSink(tmp_path / "sink.sqlite")
    original = sink.apply("op", {"v": 1}, "stable-key", 1)
    with pytest.raises(ValueError, match="different payload"):
        sink.apply("op", {"v": 2}, "stable-key", 2)
    assert len(sink.snapshot()["effects"]) == 1
    assert sink.apply("op", {"v": 1}, "stable-key", 3) == original


@pytest.mark.parametrize("mode", ["naive", "attempt-key"])
def test_unstable_identity_allows_repeated_effect(tmp_path, mode):
    sink = EffectSink(tmp_path / "sink.sqlite")
    sink.apply("op", {"v": 1}, mode, 1)
    sink.apply("op", {"v": 1}, mode, 2)
    assert len(sink.snapshot()["effects"]) == 2
