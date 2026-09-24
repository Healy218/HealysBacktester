import json

from scripts.watch_v7_catalog import estimate_eta, render


def test_recovery_eta_excludes_previous_catalog_run(tmp_path):
    history = tmp_path / "history.jsonl"
    history.write_text(json.dumps({"observed_at": "2026-09-23T00:00:00+00:00",
                                   "securities": 591, "complete_securities": 100}) + "\n")
    current = {"observed_at": "2026-09-24T20:00:00+00:00", "securities": 591,
               "complete_securities": 415, "recovery_id": "new-run"}
    assert estimate_eta(current, history) == "ETA: calculating from completed-security rate"


def test_progress_report_shows_service_state_without_recursive_size_walk():
    report = render({"proposals": 1245, "timeframe_total": 1773,
                     "features_receipts": 2490, "feature_stores": 1245,
                     "complete_securities": 415, "securities": 591,
                     "build_state": "failed", "build_exit_status": "1",
                     "build_restarts": "0", "active_logs": [],
                     "disk_free_bytes": 350 * 1024**3}, "ETA: checking")
    assert "Build service: failed (exit 1; restarts 0)" in report
    assert "Disk free: 350.0 GiB" in report


def test_eta_counts_only_runnable_securities_and_discloses_blockers(tmp_path):
    history = tmp_path / "history.jsonl"
    history.write_text(json.dumps({"observed_at": "2026-09-24T20:00:00+00:00",
                                   "securities": 591, "complete_securities": 415,
                                   "deferred_unadmitted": 45,
                                   "recovery_id": "same-run"}) + "\n")
    current = {"observed_at": "2026-09-24T21:00:00+00:00", "securities": 591,
               "complete_securities": 421, "deferred_unadmitted": 45,
               "recovery_id": "same-run"}
    assert estimate_eta(current, history).startswith("Runnable ETA: ~20.8h")
    report = render({"proposals": 1263, "timeframe_total": 1773,
                     "features_receipts": 2526, "feature_stores": 1263,
                     "complete_securities": 421, "securities": 591,
                     "deferred_unadmitted": 45, "build_state": "active",
                     "active_logs": [], "disk_free_bytes": 348 * 1024**3},
                    "Runnable ETA: ~20.8h")
    assert "Input-blocked in this run: 45 securities" in report
