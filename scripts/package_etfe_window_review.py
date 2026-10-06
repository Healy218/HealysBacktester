"""Seal a compact, source-bound ETFE window-demand evidence bundle."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def package():
    signal = ROOT/'nn_meta/validation/etfe-window-demand-20261006-r0'
    exact = ROOT/'nn_meta/validation/etfe-exact-windows-20261006-r0'
    raw = ROOT/'nn_meta/data_cache_etfe/alpaca-fresh-window-checks-20261006-r0'
    option_capture = ROOT/'nn_meta/data_cache_etfe/alpaca-fresh-exact-options-20261006-r0'
    option_normalized = ROOT/'nn_meta/data_cache_etfe/normalized-20261006-exact-options-r0'
    issuer = ROOT/'nn_meta/data_cache_etfe/issuer-fresh-invesco-20261006-r0'
    review = ROOT/'docs/reviews/2026-10-06-etfe-window-demand.md'
    spec = ROOT/'docs/specs/ETFE_WINDOW_DEMAND_20261006.md'
    reference_sources = [ROOT/p for p in (
        'scripts/build_etfe_window_demand.py','scripts/audit_etfe_context_windows.py',
        'scripts/build_etfe_exact_windows.py','scripts/audit_etfe_exact_windows.py',
        'scripts/prepare_etfe_window_checks.py','scripts/audit_etfe_window_checks.py',
        'scripts/prepare_etfe_exact_option_capture.py','scripts/audit_etfe_capture_tranche.py',
        'scripts/capture_etfe_issuer_reference.py')]
    roots = (signal, exact, raw, option_capture, option_normalized, issuer)
    files = sorted(p for folder in roots for p in folder.rglob('*') if p.is_file())
    manifest = []
    include = []
    for path in files:
        rel = path.relative_to(ROOT)
        size = path.stat().st_size
        digest = sha(path)
        include_payload = path.suffix in ('.json', '.py', '.md') and size <= 2*1024*1024
        manifest.append(dict(path=str(rel),bytes=size,sha256=digest,
            bundled=include_payload,reason=None if include_payload else 'large computational payload retained at immutable root'))
        if include_payload:
            include.append((path, rel))
    references=[dict(path=str(path.relative_to(ROOT)),bytes=path.stat().st_size,
        sha256=sha(path),bundled=True) for path in [review,spec,*reference_sources]]
    core = dict(schema='etfe-window-demand-evidence-v1',
        signal_plan_sha256=json.loads((signal/'PLAN.json').read_text())['sha256'],
        exact_plan_sha256=json.loads((exact/'PLAN.json').read_text())['sha256'],
        raw_check_plan_sha256=json.loads((raw/'PLAN.json').read_text())['sha256'],
        exact_option_capture_plan_sha256=json.loads((option_capture/'PLAN.json').read_text())['sha256'],
        exact_option_normalization_plan_sha256=json.loads((option_normalized/'PLAN.json').read_text())['sha256'],
        qqq_issuer_source_sha256=json.loads((issuer/'QQQ_RESOLUTION.json').read_text())['source_sha256'],
        artifacts=manifest,references=references,
        review=str(review.relative_to(ROOT)),spec=str(spec.relative_to(ROOT)))
    core['sha256'] = hashlib.sha256(json.dumps(core,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    output_json = ROOT/'docs/reviews/2026-10-06-etfe-window-demand.json'
    output_zip = ROOT/'docs/reviews/2026-10-06-etfe-window-demand-evidence.zip'
    output_json.write_text(json.dumps(core,indent=2,sort_keys=True)+'\n')
    with zipfile.ZipFile(output_zip,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as bundle:
        bundle.write(review,review.relative_to(ROOT))
        bundle.write(spec,spec.relative_to(ROOT))
        bundle.write(output_json,output_json.relative_to(ROOT))
        for path in [*reference_sources]:
            bundle.write(path,path.relative_to(ROOT))
        for path, rel in include:
            bundle.write(path,rel)
    return dict(manifest_sha256=core['sha256'],artifacts=len(manifest),
        bundled=sum(x['bundled'] for x in manifest),omitted=sum(not x['bundled'] for x in manifest),
        zip_bytes=output_zip.stat().st_size,zip_sha256=sha(output_zip),
        index=str(output_json.relative_to(ROOT)),bundle=str(output_zip.relative_to(ROOT)))


if __name__ == '__main__':
    print(json.dumps(package(),indent=2))
