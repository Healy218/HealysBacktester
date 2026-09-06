"""Execute actual launcher control flow with only local fake commands."""
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def executable(path, text):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text)
    path.chmod(0o755)


def test_budget_guard_does_not_treat_unknown_or_failed_cancel_as_terminal(tmp_path):
    scripts=tmp_path/'scripts'; scripts.mkdir()
    bin_dir=tmp_path/'bin'; bin_dir.mkdir()
    original=(ROOT/'scripts/cloud_budget_guard.sh').read_text()
    original=original.replace('export PATH="$HOME/google-cloud-sdk/bin:$PATH"',f'export PATH="{bin_dir}:$PATH"')
    (scripts/'cloud_budget_guard.sh').write_text(original)
    executable(tmp_path/'venv/bin/python', f'''#!{sys.executable}
import os, sys
# Only notification heredocs have one argument after '-'; discard them.
if len(sys.argv)==3 and sys.argv[1]=='-':
    sys.stdin.read()
    print('FAKE NOTIFICATION')
else:
    os.execv({sys.executable!r}, [{sys.executable!r}]+sys.argv[1:])
''')
    executable(bin_dir/'gcloud','''#!/usr/bin/env bash
case "$*" in
  'batch jobs describe '*)
    n=$(cat "$STUB_STATE/n" 2>/dev/null || echo 0)
    n=$((n+1)); echo "$n" > "$STUB_STATE/n"
    if [ "$n" -eq 1 ]; then exit 1; fi
    if [ "$n" -eq 2 ]; then echo RUNNING; else echo SUCCEEDED; fi ;;
  'batch jobs cancel '*) echo cancel >> "$STUB_STATE/cancels"; exit 1 ;;
esac
''')
    executable(bin_dir/'gsutil','#!/bin/sh\nexit 0\n')
    executable(bin_dir/'sleep','#!/bin/sh\nexit 0\n')
    env={**os.environ,'STUB_STATE':str(tmp_path),'BUDGET_USD':'0'}
    done=subprocess.run(['bash',str(scripts/'cloud_budget_guard.sh'),'fake-job'],env=env,capture_output=True,text=True,timeout=15)
    assert done.returncode==0,done.stderr
    assert (tmp_path/'n').read_text().strip()=='3'
    assert len((tmp_path/'cancels').read_text().splitlines())==2
    assert 'cancel failed' in done.stderr
    assert 'fleets CANCELLED' not in done.stdout


def test_local_upload_failure_stops_before_row_commit(tmp_path):
    source=(ROOT/'scripts/run_build_v5_local.sh').read_text()
    function=source[source.index('build_one() {'):source.index('export -f build_one')]
    executable(tmp_path/'venv/bin/python','#!/bin/sh\nexit 0\n')
    script='''set -uo pipefail
OUTB=remote; ART=art; PART=partial
mkdir -p art/meta_rows art/meta_marks partial
# Incoming optional checkpoint pulls fail; outgoing marks upload fails too.
gsutil(){
  printf '%s\\n' "$*" >> calls
  return 1
}
'''+function+'\nbuild_one SPY\n'
    done=subprocess.run(['bash','-c',script],cwd=tmp_path,capture_output=True,text=True)
    assert done.returncode==1
    calls=(tmp_path/'calls').read_text()
    assert '-q cp art/meta_marks/SPY.parquet remote/meta_marks/' in calls
    assert '-q cp art/meta_rows/SPY.parquet remote/meta_rows/' not in calls
    assert 'published' not in done.stdout


def test_cloud_marks_upload_failure_prevents_row_and_manifest_commit(tmp_path):
    source=(ROOT/'deploy/gcp/task.sh').read_text()
    start=source.rindex('  gsutil -q cp "$ART/meta_marks/${sym}.parquet"')
    block=source[start:source.index('\ndone',start)]
    script='''set -euo pipefail
ART=art; OUTB=remote; sym=SPY
gsutil(){ echo "$*" >> calls; return 1; }
'''+block
    done=subprocess.run(['bash','-c',script],cwd=tmp_path,capture_output=True,text=True)
    assert done.returncode==1
    assert len((tmp_path/'calls').read_text().splitlines())==1
    assert 'meta_marks' in (tmp_path/'calls').read_text()


def test_full_v6_freeze_preserves_validated_launcher_failure(tmp_path):
    executable(tmp_path/'scripts/run_freeze_v6_local.sh',
               (ROOT/'scripts/run_freeze_v6_local.sh').read_text())
    executable(tmp_path/'scripts/run_research_local.sh',
               '#!/usr/bin/env bash\nprintf "%s\\n" "$NN_META_V6_EXPANDED" "$@" > calls\nexit 7\n')
    env = dict(os.environ, NN_META_CAMPAIGN='expanded-test',
               NN_META_DATA_CANDIDATE='sealed-test', NN_META_V6_INPUTS='inputs.json',
               NN_META_V6_INPUTS_SHA256='a'*64)
    done = subprocess.run(['bash', str(tmp_path/'scripts/run_freeze_v6_local.sh'), '--run'],
                          cwd=tmp_path, env=env, capture_output=True, text=True)
    assert done.returncode == 7
    assert (tmp_path/'calls').read_text().splitlines() == [
        '1', '--campaign', 'expanded-test', '--pool', 'v6', '--stage', 'freeze', '--run']


def test_full_v6_freeze_cannot_start_without_feature_evidence(tmp_path):
    executable(tmp_path/'scripts/run_freeze_v6_local.sh',
               (ROOT/'scripts/run_freeze_v6_local.sh').read_text())
    env = dict(os.environ, NN_META_CAMPAIGN='expanded-test', NN_META_DATA_CANDIDATE='sealed-test')
    env.pop('NN_META_V6_INPUTS', None)
    done = subprocess.run(['bash', str(tmp_path/'scripts/run_freeze_v6_local.sh'), '--run'],
                          cwd=tmp_path, env=env, capture_output=True, text=True)
    assert done.returncode != 0 and 'reviewed TV13' in done.stderr
    assert not (tmp_path/'calls').exists()


def test_cloud_freeze_skips_only_current_contract_and_settings(tmp_path):
    import json
    from nn_meta.baseline import _config_hash
    from nn_meta.feature_contract import CONTRACT_VERSION
    source = (ROOT / 'deploy/gcp/task.sh').read_text()
    start = source.index('    if gsutil -q cp "${SPECS}/${sym}.json"')
    block = source[start:source.index('    # A symbol too thin', start)]
    executable(tmp_path / 'bin/python', f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
    script = '''set -euo pipefail
ART=art; SPECS=remote
mkdir -p "$ART"
gsutil(){ cp checkpoint.json "${@: -1}"; }
for sym in SPY; do
'''+block+'''echo REBUILD
done
'''
    cases = [({}, True),
             ({'feature_contract_version': CONTRACT_VERSION, 'config_hash': 'stale'}, True),
             ({'feature_contract_version': CONTRACT_VERSION, 'config_hash': _config_hash()}, False)]
    for spec, rebuild in cases:
        (tmp_path / 'checkpoint.json').write_text(json.dumps(spec))
        result = subprocess.run(['bash', '-c', script], cwd=tmp_path,
                                env={**os.environ, 'PATH': f'{tmp_path}/bin:'+os.environ['PATH'],
                                     'PYTHONPATH': str(ROOT)},
                                capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr
        assert ('REBUILD' in result.stdout) == rebuild
        assert ('current freeze in bucket' in result.stdout) != rebuild
