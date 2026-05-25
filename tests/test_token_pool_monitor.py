"""Tests for token pool observability monitor."""

from __future__ import annotations

from backend.services.token_pool_monitor import TokenPoolMonitor


def test_monitor_tracks_switch_and_failure():
    monitor = TokenPoolMonitor()
    monitor.begin_run("intake-1", ["alpha", "beta"], total_chunks=10)
    monitor.set_current_chunk(3)
    monitor.record_token_used("alpha", 3)
    monitor.record_quota_failure("alpha", 3)
    monitor.record_switch("alpha", "beta", "429_quota", 3)
    monitor.record_chunk_success("beta", 3)

    snap = monitor.snapshot()
    assert snap["generation_active"] is True
    assert snap["now_using"] == "beta"
    assert "alpha" in snap["failed_tokens"]
    assert len(snap["switch_history"]) == 1
    assert snap["switch_history"][0]["to_token"] == "beta"
    assert any(item["status"] == "calling" for item in snap["usage_history"])

    monitor.end_run()
    assert monitor.snapshot()["generation_active"] is False
