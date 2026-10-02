from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from scripts.v7_discovery_resources_v2 import worker_limit
from scripts.run_v7_execution_recovery_v2 import capacity, empty_job
from tests.test_v7_execution_recovery import fixture_jobs


def at(hour):
    return datetime(2026, 10, 2, hour, tzinfo=ZoneInfo('America/Chicago'))


def test_four_workers_fit_overnight_and_cpu_limit_is_preserved():
    assert worker_limit(now=at(1), available_mib=26000, autosized=4) == 4
    assert worker_limit(now=at(1), available_mib=26000, autosized=2) == 2


def test_paper_and_daily_incubator_hours_reduce_admissions():
    assert worker_limit(now=at(7), available_mib=30000, autosized=4) == 2
    assert worker_limit(now=at(20), available_mib=30000, autosized=4) == 2
    assert worker_limit(now=at(21), available_mib=30000, autosized=4) == 4


def test_low_memory_waits_instead_of_autosize_floor_one():
    assert worker_limit(now=at(1), available_mib=14000, autosized=1) == 0
    assert worker_limit(now=at(1), available_mib=19000, autosized=4) == 2
    assert worker_limit(now=at(8), available_mib=21000, autosized=1) == 0


def test_larger_concurrency_still_reserves_disk_for_each_writer(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr('scripts.run_v7_execution_recovery_v2.shutil.disk_usage',
                        lambda _: SimpleNamespace(free=10_000_000_000 + 1800 * 1024**2))
    assert capacity('.', 3)
    with pytest.raises(ValueError, match='reserve'):
        capacity('.', 4)


def test_empty_demand_still_requires_matching_rows(tmp_path):
    with pytest.raises(ValueError, match='Empty queue'):
        empty_job(fixture_jobs(tmp_path, rows=1))
