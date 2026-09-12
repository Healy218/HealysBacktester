"""Bounded, read-only training library. Research artifacts never enter the web bundle.

Receipts bind the explicitly configured continuation; we do not pick newest runs,
import training code, load weights, or read the multi-GB parent campaign scope.
"""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re

LIMIT = 1_000_000
HISTORICAL = 'Historical, pre-audit results. September 5–6 corrections require rebuilt artifacts; these returns are not corrected performance evidence.'


def read(path):
    with Path(path).open('rb') as f:
        raw = f.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError('Training input exceeds size limit')
    return raw


def obj(path):
    return json.loads(read(path))


def optional(path):
    try:
        return obj(path)
    except FileNotFoundError:
        return None


def pct(value):
    return '—' if value is None else f'{value * 100:+.1f}%'


def decimal(value, digits=4):
    return '—' if value is None else f'{value:.{digits}f}'


def number(value):
    return '—' if value is None else f'{value:,}'


def table(title, columns, rows, note=''):
    return dict(title=title, columns=columns, rows=[[str(x) if x is not None else '—' for x in row] for row in rows], note=note)


def report(version, title, summary):
    return dict(id=version, label='V3.1' if version == 'v31' else version.upper(), title=title,
                status='Historical', summary=summary, notes=[HISTORICAL], facts=[], folds=[], tables=[], sources=[])


def source(root, rel, target, start=None, end=None):
    raw = read(root / rel)
    content = raw.decode('utf-8')
    if start:
        content = content.split(start, 1)[1]
        if end:
            content = content.split(end, 1)[0]
        content = start + content
    item = dict(path=rel, sha256=hashlib.sha256(raw).hexdigest(), content=content,
                excerpt=bool(start))
    target['sources'].append(item)
    return content


def fold(label, period, policy, ret, dd=None, baseline=None, ex=None, trades=None, basis='Legacy simulation'):
    return dict(label=label, period=period, policy=policy, returnValue=ret, drawdown=dd,
                baseline=baseline, exTop3=ex, trades=trades, basis=basis)


def legacy(root, version):
    r = report(version, 'Original meta filter' if version == 'v2' else 'Small-universe meta ensemble',
               'Beat the fold-frozen baseline in all three archived folds; beat the underlying basket in two. The first fold was weak, and the reports use the older data and accounting contract.')
    rel = 'nn_meta/reports/meta_report.md' if version == 'v2' else 'nn_meta/reports_v3/meta_report.md'
    text = source(root, rel, r)
    section = text.split('## Walk-forward folds', 1)[1]
    for line in section.splitlines():
        cells = [x.strip() for x in line.strip('|').split('|')]
        if not re.match(r'^\| [123] \|', line):
            continue
        def value(cell):
            return float(re.search(r'([+-]?[\d.]+)%', cell)[1]) / 100
        r['folds'].append(fold('Fold ' + cells[0], cells[2], 'NN / fold-frozen policy',
                              value(cells[3]), baseline=value(cells[5]), ex=value(cells[4]),
                              trades=int(re.search(r'\((\d+)\)', cells[3])[1])))
    r['facts'] = [dict(label='Universe', value='56 symbols / 4 strategies' if version == 'v2' else '55 symbols / 7 strategies'),
                  dict(label='Protocol', value='3 folds / proposals re-frozen per fold'),
                  dict(label='Report era', value='July 2026'),
                  dict(label='Dataset', value='Not retained in this summary' if version == 'v2' else '344,780 rows')]
    r['notes'].append('Missing drawdowns are unreported, not zero. Basket buy-and-hold has different exposure from the options portfolio.')
    if version == 'v3':
        r['notes'].append('The archived report title says v2.1; its reports_v3 path and the EXPERIMENTS scoreboard identify this as v3. The source title is preserved. Its score-quintile mean returns are not monotone.')
        r['tables'].append(table('One-shot test · separate from walk-forward', ['Policy', 'Return', 'Max drawdown', 'Trades', 'Ex-top3'],
                                [['NN rank / 1× costs', '+257.9%', '23.4%', '192', '+93.4%'],
                                 ['NN rank / 2× costs', '+237.2%', '23.7%', '192', '+82.3%'],
                                 ['Frozen-DTE baseline', '+896.1%', '29.5%', '149', '+359.8%']],
                                '40-seed ensemble, threshold 0.6. This one-shot test did not beat the options baseline. The exact test dates are not recorded in this Markdown report.'))
    source(root, 'docs/EXPERIMENTS.md', r, '## Backtest / walk-forward verdicts', '## Live experts')
    return r


def v31(root):
    r = report('v31', 'Expanded universe, fragile outliers',
               'The larger pool passed the historical two-of-three-fold bar, but one TQQQ trade dominated fold 2 and fold 3 lost money. The archive explicitly declined to treat it as a clear upgrade over v3.')
    r['facts'] = [dict(label='Universe', value='118 eligible / 120 requested'), dict(label='Strategies', value='5 pools'),
                  dict(label='Training grid', value='320 runs / 40 seeds per configuration'), dict(label='Training wall time', value='About 20 hours / CPU')]
    r['folds'] = [fold('Fold 1', '2025-07-18 → 2025-11-06', 'NN / rank 0.55', 2.276, baseline=.096, trades=201),
                  fold('Fold 2', '2025-11-07 → 2026-03-05', 'NN / rank 0.55', 11.359, baseline=.907, ex=.177, trades=190),
                  fold('Fold 3', '2026-03-06 → 2026-06-29', 'NN / rank 0.55', -.257, baseline=2.990, ex=-.612, trades=109)]
    r['tables'] = [table('One-shot selection test', ['Model', 'Return', 'Max drawdown', 'Trades', 'Ex-top3'],
                        [['NN / rank 0.55', '+499.4%', '10.8%', '178', '+344.5%'], ['Baseline', '+279.5%', '56.0%', '—', '—']],
                        '40-seed ensemble; 36/40 seeds passed selection. Doubled costs returned +465.4%. Separate test from the walk-forward folds.'),
                   table('Training configuration', ['Setting', 'Recorded value'],
                         [['Winner', 'label_excess / 32×16 / learning rate 0.0003'],
                          ['Grid', '2 labels × 2 architectures × 2 learning rates × 40 seeds'],
                          ['Dataset splits', '368,455 train / 61,620 validation / 59,180 test rows'],
                          ['Calibration concern', 'Win probability rises with score; mean payoff falls in the top quintile']])]
    r['notes'].append('The original reports_v31 files are not present locally. This summary uses the preserved run history; no missing metrics are reconstructed.')
    source(root, 'docs/v31_run_history.md', r)
    return r


def v4(root):
    r = report('v4', 'Causal features and portfolio accounting',
               'V4 added purged selection, portfolio mark-to-market accounting, calibration and an expected-return head. The August 21 walk-forward still suffered a losing shock-period fold. Earlier July results are retained separately below.')
    r['facts'] = [dict(label='Universe', value='118 symbols / v31 data'), dict(label='Protocol', value='Nested, purged walk-forward'),
                  dict(label='Summary run', value='August 21, 2026 / EV head'), dict(label='Selection', value='Ledger / EV policy in all 3 folds')]
    r['folds'] = [fold('Fold 1', 'Dates not retained in local EV summary', 'EV / fold-selected', 5.52, .26, basis='Marked ledger (rounded archive)'),
                  fold('Fold 2', 'Dates not retained in local EV summary', 'EV / fold-selected', -.015, .69, basis='Marked ledger (rounded archive)'),
                  fold('Fold 3', 'Dates not retained in local EV summary', 'EV / fold-selected', 1.35, .45, basis='Marked ledger (rounded archive)')]
    r['tables'] = [table('August EV run · shared simulation', ['Fold', 'Return', 'Max drawdown'],
                        [['1', '+485%', '23%'], ['2', '−11%', '75%'], ['3', '+159%', '32%']],
                        'Rounded archived metrics. Shared simulation and marked ledger returns are distinct accounting views.'),
                  table('Earlier July 21 run · shared simulation', ['Fold', 'Winner', 'Return', 'Ex-top3', 'Max drawdown'],
                        [['1', 'NN / filter 0.55', '+754.6%', '+340.7%', '25.5%'], ['2', 'GBT / filter 0.50', '+354.3%', '+287.3%', '48.7%'], ['3', 'NN / rank 0.50', '+117.4%', '+36.9%', '25.0%']],
                        'A different earlier run, before ledger selection; do not mix these folds with the August EV run.')]
    r['notes'] += ['Local reports_v31 JSON/Markdown files are absent; preserved documentation is the source. Exact August fold dates and unreported metrics remain unavailable.',
                   'The August 21 finalization was refused for failing the baseline-return term. The earlier claim that drawdown caused that refusal was explicitly retracted in EXPERIMENTS.',
                   'Historical deployment notes refer to their own dates. They do not establish current production eligibility.']
    source(root, 'docs/EXPERIMENTS.md', r, '## 2026-08-21 (evening)', '## Backtest / walk-forward verdicts')
    source(root, 'docs/specs/V4_OUTLINE.md', r, '**Nested 3-fold walk-forward**', '## Stage 1')
    return r


def modern_folds(r, rows):
    validation, calibration, families, splits, scores, evs = [], [], [], [], [], []
    for i, row in enumerate(rows, 1):
        w = row['winner']; window = row['window']; test = w.get('test', {}); marked = w.get('marked') or {}
        policy = f"{w['family'].upper()} / {w['mode']} {w['threshold']}"
        basis = 'Marked ledger / base costs' if marked else 'Shared simulation / base costs'
        r['folds'].append(fold(f'Fold {i}', f"{window['test_start']} → {window['test_end']}", policy,
                              (marked or test).get('total_return'), (marked or test).get('max_drawdown'),
                              trades=test.get('n_kept'), basis=basis))
        validation.append([i, window['val_start'], policy, pct(w.get('validation', {}).get('total_return')),
                           pct(w.get('validation', {}).get('max_drawdown')), pct(w.get('baseline_return')),
                           'Eligible' if w.get('eligible') else 'Rejected', pct(test.get('total_return')), pct(test.get('total_ex_top3'))])
        cal = w.get('calibration', {}); pbo = w.get('pbo', {}); dsr = w.get('deflated_sharpe', {})
        calibration.append([i, cal.get('method'), decimal(cal.get('brier_raw')), decimal(cal.get('brier_calibrated')),
                            decimal(pbo.get('pbo')), decimal(dsr.get('deflated_sharpe')),
                            str((w.get('score_deciles') or {}).get('inverted', 'Unknown')),
                            str((w.get('ev_deciles') or {}).get('inverted', 'Unknown'))])
        for family, model in row.get('models', {}).items():
            val = model.get('validation') or {}; tst = model.get('test') or {}
            families.append([i, family.upper(), f"{model['mode']} {model['threshold']}", number(val.get('n_kept')),
                             pct(val.get('total_return')), number(tst.get('n_kept')), pct(tst.get('total_return'))])
        for split in row.get('split_summary', []):
            splits.append([i, split['split'], number(split.get('rows')), split.get('first_entry'), split.get('last_entry')])
        for key, target in [('score_deciles', scores), ('ev_deciles', evs)]:
            for d in (w.get(key) or {}).get('deciles', []):
                target.append([i, d['decile'], number(d['n']), decimal(d['mean_score']), pct(d['win_rate']), pct(d['mean_return'])])
    r['tables'] += [table('Validation selection & separate test accounting', ['Fold', 'Validation starts', 'Winner', 'Val return', 'Val drawdown', 'Val baseline', 'Val gate', 'Test simulation', 'Test simulation ex-top3'], validation,
                         'The baseline column is validation-only. No matching held-out baseline is supplied in these JSON reports; it is never substituted into the out-of-sample table.'),
                   table('Calibration & selection diagnostics', ['Fold', 'Calibration', 'Raw Brier', 'Calibrated Brier', 'PBO', 'Deflated Sharpe', 'Score inverted', 'EV inverted'], calibration,
                         'PBO estimates selection overfitting; Brier measures probability error. Deflated Sharpe adjusts for tried policies. These are diagnostics, not deployment approvals.'),
                   table('Neural network vs boosted trees', ['Fold', 'Family', 'Policy', 'Val trades', 'Val return', 'Test trades', 'Test return'], families,
                         'Shared-simulation test returns for each family. Zero trades and missing returns stay distinct.'),
                   table('Temporal splits after purge', ['Fold', 'Split', 'Rows', 'First entry', 'Last entry'], splits),
                   table('Probability-score deciles', ['Fold', 'Decile', 'Candidates', 'Mean score', 'Win rate', 'Mean return'], scores),
                   table('Expected-return deciles', ['Fold', 'Decile', 'Candidates', 'Mean score', 'Win rate', 'Mean return'], evs)]


def ensemble(r, config, historical=False):
    r['tables'].append(table('Final ensemble · validation tail', ['Setting', 'Recorded result'], [
        ['Family / policy', f"{config['family'].upper()} / {config['mode']} {config['threshold']}"],
        ['Seeds / features', f"{len(config['final_seeds'])} / {len(config['features'])}"],
        ['Return / max drawdown', f"{pct(config['val_return'])} / {pct(config['val_max_drawdown'])}"],
        ['Kept trades', number(config['val_n_kept'])], ['Gate / eligible', f"{config.get('gate_bar', 'legacy')} / {config['eligible']}"],
        ['Operating point', config.get('operating_point_source', 'Not recorded')],
        ['Target / embargo', f"{config.get('label')} / {config.get('embargo')}"],
        ['Feature columns', ', '.join(config['features'])]],
        ('Historical gate result. ' if historical else '') + 'This tail selects and revalidates the operating point; it is not another held-out test. Completion does not deploy the model.'))


def v5(root):
    r = report('v5', 'Wide pool and expected-return sizing',
               'All three archived folds selected an eligible neural policy. Marked returns were positive in each, with material drawdown in the first two. The final 40-seed ensemble passed the adopted historical risk gate.')
    r['facts'] = [dict(label='Universe', value='441 eligible / 453 requested'), dict(label='Strategies', value='10 families'),
                  dict(label='Final ensemble', value='40 neural seeds / 48 features'), dict(label='Report era', value='September 4–5, 2026')]
    rows = obj(root / 'nn_meta/reports_v5/v4_walkforward_report.json'); modern_folds(r, rows)
    ensemble(r, obj(root / 'nn_meta/model_final_v5/ensemble_config.json'), True)
    r['notes'].append('This is the original walk-forward report, not the later threshold-0.45 sweep. Fold dates differ from v4 and v6. The old final gate pass predates the corrective audit.')
    source(root, 'nn_meta/reports_v5/v4_walkforward_report.md', r)
    source(root, 'docs/EXPERIMENTS.md', r, '## 2026-09-04 — v5 wide pool WALK-FORWARD', '## 2026-08-29')
    return r


def checked(root, base, stage, relative):
    receipt = obj(base / f'runs/continuation/{stage}.json')
    path = base / relative
    raw = read(path)
    expected = receipt.get('outputs', {}).get(str(path.relative_to(root)))
    if receipt.get('returncode') != 0 or expected != hashlib.sha256(raw).hexdigest():
        raise ValueError(f'{stage} report binding failed')
    return json.loads(raw) if path.suffix == '.json' else raw.decode()


def processes(campaign, proc=Path('/proc')):
    found = []
    modules = {'scripts.continue_v6_training', 'nn_meta.v4_evaluate', 'nn_meta.v4_finalize',
               'nn_meta.training_jobs', 'nn_meta.training_experiments', 'nn_meta.build_meta_dataset'}
    for p in proc.iterdir():
        if not p.name.isdigit():
            continue
        try:
            args = (p / 'cmdline').read_bytes().decode().split('\0')
            if '-m' not in args:
                continue
            module = args[args.index('-m') + 1]
            if module not in modules:
                continue
            env = (p / 'environ').read_bytes().split(b'\0')
            bound = f'NN_META_CAMPAIGN={campaign}'.encode() in env and b'NN_META_POOL=v6' in env
            if module == 'scripts.continue_v6_training':
                bound = '--campaign' in args and args[args.index('--campaign') + 1] == campaign
            if bound and (p / 'stat').read_text().rsplit(')', 1)[1].split()[0] != 'Z':
                found.append(module)
        except (OSError, UnicodeError, IndexError):
            continue
    return found


def live(root, campaign):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', campaign):
        raise ValueError('Invalid training campaign')
    base = root / 'nn_meta/campaigns' / campaign / 'v6'
    scope = obj(base / 'continuation_scope.json'); latest = obj(base / 'runs/continuation/latest.json')
    if scope.get('campaign') != campaign or latest.get('campaign') != campaign:
        raise ValueError('Training campaign binding failed')
    r = report('v6', 'Expanded features, bounded training',
               'Evaluation compares neural networks and boosted trees across three post-freeze folds. Final family selection, 40-seed training and gate revalidation follow. The summary updates from this campaign’s receipts.')
    r['notes'] = ['Research-only: external TradingView parity remains deferred. This is conditional meta evaluation on globally frozen proposals, not a full system refrozen within each fold.',
                  'The final validation tail is reused for operating-point selection and is not a new held-out test. No v6 deployment is performed by this dashboard.']
    stage = latest.get('stage', 'complete'); state = latest['status']; active = processes(campaign)
    finals = list((base / 'model_final.staging').glob('*/complete.json'))
    if (base / 'model_final/manifest.json').exists():
        finals = list((base / 'model_final').glob('*/complete.json'))
    activity = f'{stage}: running' if active else f'{stage}: no process visible; last receipt says {state}'
    r['status'] = 'Training' if state == 'running' else state.replace('_', ' ').capitalize()
    if state == 'failed':
        final_receipt = optional(base / 'runs/continuation/finalize.json') or {}
        log = base / 'runs/continuation/finalize.log'
        if stage == 'finalize' and final_receipt.get('returncode') == 1 and log.exists() and 'NO ELIGIBLE CONFIG' in read(log).decode():
            r['status'] = 'Gate rejected'
            r['summary'] = 'Training finished, but the full ensemble did not pass the configured final gate. Completed fold results remain available. The staged models are retained for investigation; no final bundle was promoted.'
        else:
            r['status'] = 'Failed'
        activity = f"{r['status']} during {stage}; receipt exit {latest.get('returncode', 'unknown')}"
    training = scope['training']
    r['facts'] = [dict(label='Campaign', value=campaign), dict(label='Universe', value=f"{len(scope['symbols'])} eligible symbols"),
                  dict(label='Concurrency', value=f"{training['workers']} seed workers × {training['threads']} threads"),
                  dict(label='Final seeds', value=f"{len(finals)} / {len(training['final_seeds'])}")]
    r['tables'].append(table('Training design', ['Setting', 'Value'], [
        ['Parent build', scope['parent']], ['Feature contract', scope['feature_contract_version']],
        ['Target', training['label']], ['Training budget', f"{training['epochs']} NN epochs / {training['trees']} boosted trees"],
        ['Selection seeds', ', '.join(map(str, training['selection_seeds']))],
        ['Validation', f"{training['validation_days']} sessions / one-day embargo / exit-time purge"],
        ['Memory strategy', 'Shared read-only arrays, bounded preparation, streamed joins and one-member-at-a-time prediction'],
        ['Resume', 'Source/input-bound stage receipts and per-seed checkpoints']]))
    if (optional(base / 'runs/continuation/assemble.json') or {}).get('returncode') == 0:
        assembled = checked(root, base, 'assemble', 'artifacts/meta_dataset.assembly.json')
        r['facts'] += [dict(label='Retained dataset rows', value=number(assembled['dataset_rows'])),
                       dict(label='Intratrade marks', value=number(assembled['mark_rows']))]
        r['tables'].append(table('Dataset assembly', ['Step', 'Rows'],
                                [['Built inputs', number(assembled['input_rows'])],
                                 ['After point-in-time membership', number(assembled['membership_rows'])],
                                 ['After static purge', number(assembled['dataset_rows'])],
                                 ['Intratrade marks', number(assembled['mark_rows'])]]))
    for stage_name in ['assemble', 'experiments', 'evaluate', 'finalize']:
        receipt = optional(base / f'runs/continuation/{stage_name}.json')
        if receipt:
            r['facts'].append(dict(label=f'{stage_name.capitalize()} stage', value=f"Exit {receipt['returncode']}" + (f" / {receipt['seconds'] / 60:.1f} min" if 'seconds' in receipt else ' / verified reuse')))
    if (optional(base / 'runs/continuation/evaluate.json') or {}).get('returncode') == 0:
        rows = checked(root, base, 'evaluate', 'reports/evaluate.json')
        checked(root, base, 'evaluate', 'reports/evaluate.manifest.json')
        checked(root, base, 'evaluate', 'reports/evaluate.md')
        modern_folds(r, rows)
        source(root, str((base / 'reports/evaluate.md').relative_to(root)), r)
        eligible = sum(row['winner'].get('eligible') is True for row in rows)
        families = ', '.join(sorted({row['winner']['family'].upper() for row in rows}))
        r['summary'] = f'{eligible} of {len(rows)} evaluation folds selected a gate-eligible policy ({families}). The corresponding marked test returns and drawdowns are shown below. Final ensemble training and gate status are tracked separately.'
        if r['status'] == 'Gate rejected':
            r['summary'] += ' Final gate revalidation rejected the ensemble.'
    comparisons = base / 'reports/objective-comparisons/results.json'
    if comparisons.exists() and (optional(base / 'runs/continuation/experiments.json') or {}).get('returncode') == 0:
        results = checked(root, base, 'experiments', 'reports/objective-comparisons/results.json')
        # Preserve all recorded experiment metrics without reinterpreting their units.
        r['tables'].append(table('Objective comparisons · recorded metrics', ['Result', 'Value'], flatten(results),
                                 'Separate held-out objective study. Event balancing was mixed; the baseline objective was retained. Lower downside-Q10 pinball loss is promising, but is not a portfolio gate.'))
    if state == 'complete':
        for stage_name in ('assemble', 'experiments', 'evaluate', 'finalize'):
            if obj(base / f'runs/continuation/{stage_name}.json').get('returncode') != 0:
                raise ValueError('Incomplete stage receipts')
        config = checked(root, base, 'finalize', 'model_final/ensemble_config.json')
        checked(root, base, 'finalize', 'model_final/manifest.json')
        if config.get('eligible') is not True:
            raise ValueError('Final eligibility mismatch')
        ensemble(r, config)
        r['status'] = 'Complete · research only'
        r['summary'] += f" The final {len(config['final_seeds'])}-seed {config['family'].upper()} ensemble passed its configured validation gate. It has not been deployed."
        activity = 'Completed; final report and configuration match the recorded stage hashes'
    if state in ('complete', 'failed'):
        log = read(base / 'runs/continuation/finalize.log').decode()
        if '=== re-validating' in log:
            r['sources'].append(dict(path=str((base / 'runs/continuation/finalize.log').relative_to(root)),
                                     sha256=hashlib.sha256(log.encode()).hexdigest(), excerpt=True,
                                     content='## Final ensemble gate log\n\n```text\n' + log.split('=== re-validating', 1)[1][-18000:] + '\n```'))
    source(root, 'docs/reviews/2026-09-12-v6-training.md', r)
    nn_receipts = list((base / 'runs/seed-jobs').glob('*/nn-s*/complete.json'))
    failed_nn = sum(not isinstance(loss := obj(path).get('val_loss'), (int, float))
                    or isinstance(loss, bool) or not math.isfinite(loss) for path in nn_receipts)
    if failed_nn:
        warning = (f'Training health: {failed_nn} of {len(nn_receipts)} completed neural runs have missing or non-finite validation loss. '
                   'The neural-versus-GBT comparison is invalid; zero neural trades are not evidence of a healthy model losing. '
                   'Scanner promotion needs review despite the recorded GBT gate pass.')
        r['notes'].insert(0, warning)
        r['summary'] += ' Neural training health failed; review the caveat below before interpreting family selection.'
        if state == 'complete':
            r['status'] = 'Complete · review required'
    review = root / 'docs/reviews/2026-09-12-v6-deployment-review.md'
    if campaign == 'v6-train-20260912r2' and review.exists():
        source(root, str(review.relative_to(root)), r)
    return r, dict(status=r['status'], stage=latest.get('stage', 'complete'), activity=activity,
                   activeWorkers=active.count('nn_meta.training_jobs'), completedFinalSeeds=len(finals), totalFinalSeeds=len(training['final_seeds']),
                   totalSymbols=len(scope['symbols']), selectionSeedJobs=len(list((base / 'runs/seed-jobs').glob('*/*/complete.json'))),
                   evidence=dict(assembled_dataset=(optional(base / 'runs/continuation/assemble.json') or {}).get('returncode') == 0,
                                 evaluation_report=bool(r['folds']), final_model_manifest=state == 'complete'))


def flatten(value, prefix=''):
    rows = []
    if isinstance(value, dict):
        for key, child in value.items():
            rows.extend(flatten(child, f'{prefix} / {key}' if prefix else key))
    elif isinstance(value, list):
        if len(value) < 20:
            for i, child in enumerate(value):
                rows.extend(flatten(child, f'{prefix} / {i}'))
        else:
            rows.append([prefix, f'{len(value)} items; see campaign source'])
    else:
        rows.append([prefix, decimal(value, 6) if isinstance(value, float) else str(value)])
    return rows


def collect_training(root, campaign, now=None):
    root = Path(root); now = now or datetime.now(timezone.utc)
    result = dict(observedAt=now.isoformat(), campaign=campaign, status='Unavailable', stage='unknown',
                  activity='Training receipts unavailable', activeWorkers=None, completedFinalSeeds=None,
                  totalFinalSeeds=None, versions=[], issues=[])
    for version, loader in [('v2', lambda: legacy(root, 'v2')), ('v3', lambda: legacy(root, 'v3')),
                            ('v31', lambda: v31(root)), ('v4', lambda: v4(root)), ('v5', lambda: v5(root)),
                            ('v6', lambda: live(root, campaign))]:
        try:
            value = loader()
            if version == 'v6':
                value, status = value
                result.update(status)
            result['versions'].append(value)
        except (OSError, ValueError, KeyError, TypeError, IndexError):
            r = report(version, 'Report unavailable', 'A required source is missing, unreadable, or failed its campaign binding. No performance metrics are shown for this version.')
            r['status'] = 'Unavailable'; r['notes'] = []; result['versions'].append(r)
            result['issues'].append(f'{version}: report unavailable or failed integrity check')
    return result
