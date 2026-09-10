"""Run exit watches sequentially with each expert's own data-pool setting."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from nn_meta.live.alert_batches import Batches
    queue = Batches()
    with queue.path.with_suffix('.taken-monitor.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        with queue.connect() as db:
            experts = {json.loads(r[0])['expert'] for r in db.execute("SELECT context FROM taken_trades WHERE status='open'")}
        for expert in sorted(experts):
            pool = 'v31' if expert == 'v4' else expert
            if pool not in ('v3', 'v31', 'v5'):
                continue
            env = dict(os.environ, NN_META_POOL=pool, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
            try:
                result = subprocess.run([sys.executable, '-m', 'nn_meta.live.taken_monitor', '--expert', expert], cwd=ROOT, env=env, timeout=180)
                if result.returncode:
                    print(f'Exit monitor [{expert}] failed: exit {result.returncode}', flush=True)
            except subprocess.TimeoutExpired:
                print(f'Exit monitor [{expert}] exceeded 180 seconds', flush=True)


if __name__ == '__main__':
    main()
