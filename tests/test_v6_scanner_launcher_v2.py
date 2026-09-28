import os
import pytest
from pathlib import Path
import subprocess


@pytest.mark.parametrize('version,expected', [('v2', '4'), ('v3', '8')])
def test_numerical_thread_setting_does_not_force_serial_process_sizing(tmp_path,version,expected):
    cpu = tmp_path / 'nproc'
    cpu.write_text('#!/bin/sh\nif [ -n "${OMP_NUM_THREADS:-}" ]; then echo 1; else echo 16; fi\n')
    cpu.chmod(0o755)
    memory = tmp_path / 'awk'
    memory.write_text('#!/bin/sh\necho 32768\n')
    memory.chmod(0o755)
    env = {**os.environ, 'PATH': str(tmp_path)+':'+os.environ['PATH'],
           'OMP_NUM_THREADS': '1', 'OMP_THREAD_LIMIT': '1'}
    result = subprocess.run(['bash', f'scripts/run_v6_alpaca_scanner_{version}.sh', '--print-workers'],
                            cwd=Path(__file__).resolve().parents[1], env=env,
                            check=True, capture_output=True, text=True)
    # Service memory limits still cap the count despite 16 available CPUs.
    assert result.stdout.splitlines()[-1] == expected
