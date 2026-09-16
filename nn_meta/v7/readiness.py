"""Fail-closed aggregation of full-universe V7 preparation evidence.

Stage producers must publish immutable, source-bound evidence with the current
scope. Component tests, old pilots and successful downloads cannot substitute.
This checker does not manufacture missing stage evidence or launch training.
"""
import json
from pathlib import Path

from nn_meta.v7.storage import sha, identity, verify
from nn_meta.v7.rows import ROW_CONTRACT, schema
from nn_meta.v7.scope import HISTORY_START, HISTORY_END, require_active_inputs
from nn_meta.v7.provenance import source_manifest, runtime_manifest

REQUIRED = {
    'lifecycle': ('all_sessions_classified', 'dated_aliases_consumed', 'dated_sectors_complete',
                  'held_positions_across_lifecycle_resolved'),
    'causal_prices': ('all_securities_covered', 'publication_and_effective_evidence',
                      'combined_actions_and_spinoffs', 'contemporaneous_tick_units', 'cross_action_stops'),
    'daily_context': ('all_securities_covered', 'price_state_starts_march15', 'warmup_missingness_recorded',
                      'market_and_sector_context', 'first_eligible_observations_recorded'),
    'quotes': ('actual_interval_union', 'entries_marks_exits_rolls_exercise_covered',
               'trade_features_covered', 'dated_class_hours_and_weeklies', 'shared_quota_under_250gb'),
    'physical_execution': ('dated_official_exercise_references', 'dated_deliverables', 'shared_funding',
                           'settlement_calendar', 'observed_alpaca_stock_liquidation',
                           'all_outcomes_resolved', 'full_cash_reconciliation'),
    'assembly': ('full_history_all_variants', '222_columns', 'complete_label_and_mark_lineage',
                 'fold_purging_through_settlement', 'bounded_training_sequences', 'recovery_verified'),
    'trials': ('runnable_predeclared_manifest', 'fair_baselines', 'finite_nn_and_gbt',
               'deterministic_seeds', 'train_only_calibration_and_weights', 'multiple_testing_accounting'),
    'integrated_pilots': ('new_window', 'sparse_and_liquid', 'actions_aliases_early_closes',
                          'rolls_and_funded_expiry', 'four_bounded_workers', 'binned_dataset_memory',
                          'no_swap_growth', 'v6_coexistence'),
}


def scope_binding(active):
    return identity({k: active.get(k) for k in ('history_start', 'history_end', 'working_inputs',
        'input_report_sha256', 'chain_receipt_sha256', 'universe_receipt_sha256',
        'coverage_receipt_sha256', 'evaluation_file_sha256', 'plan_file_sha256',
        'universe_exclusions_sha256')} | {'row_contract': ROW_CONTRACT})


def assess(root, active_path):
    root, active_path = Path(root), Path(active_path)
    active = json.loads(active_path.read_text())
    gates = []
    def check(name, function):
        try:
            detail = function()
        except (ValueError, OSError, KeyError, TypeError) as exc:
            gates.append(dict(gate=name, passed=False, reason=str(exc)))
        else:
            gates.append(dict(gate=name, passed=True, evidence=detail))
    def inputs():
        if (active['history_start'], active['history_end']) != (HISTORY_START, HISTORY_END):
            raise ValueError('Active date scope differs')
        source = root / active['working_inputs']
        require_active_inputs(source)
        for path, digest in ((source/'report.json', active['input_report_sha256']),
                (root/active['verification'], active['verification_sha256']),
                (root/active['chain']/'complete.json', active['chain_receipt_sha256']),
                (root/active['evaluation'], active['evaluation_file_sha256']),
                (root/active['plan'], active['plan_file_sha256'])):
            if sha(path) != digest:
                raise ValueError(f'Active input hash differs: {path}')
        return {'scope_identity': scope_binding(active), 'feature_columns': len(schema())}
    check('active_inputs', inputs)
    universe = None
    def membership():
        nonlocal universe
        import pandas as pd
        path = root / active['universe']
        verify(path)
        if sha(path/'complete.json') != active['universe_receipt_sha256']:
            raise ValueError('Universe receipt changed')
        report = json.loads((path/'report.json').read_text())
        if not report['identity_boundaries_verified']:
            raise ValueError('Unresolved reviewed identity boundaries')
        expected = ['2022-03-08', '2022-03-09', '2022-03-10', '2022-03-11', '2022-03-14']
        if report['lookback_policy']['excluded_sessions'] != expected:
            raise ValueError('Universe has not applied the deleted-session policy')
        provenance = json.loads((path/'provenance.json').read_text())
        for name, digest in provenance['code'].items():
            if sha(root/name) != digest:
                raise ValueError('Universe builder source changed; rebuild required')
        universe = pd.read_parquet(path/'membership.parquet')
        symbols = sorted(set(universe[universe.month >= '2022-02'].ticker))
        plan = json.loads((root/active['plan']).read_text())['plan']
        from nn_meta.multitimeframe_catalog import registered_catalog
        if (plan.get('plan_sha256') != identity({k:v for k,v in plan.items() if k != 'plan_sha256'})
                or plan.get('plan_sha256') != active.get('plan_sha256')
                or plan.get('catalog') != registered_catalog(symbols)
                or plan.get('membership_receipt_sha256') != active['universe_receipt_sha256']):
            raise ValueError('Training plan does not bind the complete current universe and variant catalog')
        if active.get('universe_exclusions'):
            excluded_path = root/active['universe_exclusions']
            digest = sha(excluded_path)
            excluded = json.loads(excluded_path.read_text())
            ids = sorted(e['security_id'] for e in excluded['exclusions'])
            if (digest != active.get('universe_exclusions_sha256')
                    or report.get('exclusion_declaration_sha256') != digest
                    or report.get('excluded_security_ids') != ids
                    or plan.get('universe_exclusions_sha256') != digest
                    or universe.security_id.isin(ids).any()
                    or excluded.get('historically_known_eligibility') is not False):
                raise ValueError('User study exclusions are absent, changed or disguised as PIT eligibility')
        return {k:report[k] for k in ('historical_symbols', 'historical_securities', 'rows')}
    check('rebuilt_membership', membership)
    def coverage():
        path = root/active['coverage_inventory']
        verify(path)
        if sha(path/'complete.json') != active['coverage_receipt_sha256']:
            raise ValueError('Coverage receipt changed')
        report = json.loads((path/'report.json').read_text())
        if report['sources'].get(str(root/active['universe']/'complete.json'),
                report['sources'].get(str(Path(active['universe'])/'complete.json'))) != active['universe_receipt_sha256']:
            raise ValueError('Coverage was computed using another universe')
        # These zeros remain visible even if a later lifecycle report explains
        # expected absence. That later report must account for every such case.
        return {k:report[k] for k in ('eligible_sessions', 'resolved_alias_sessions', 'remaining_zero_sessions')}
    check('coverage_inventory', coverage)
    scope = scope_binding(active)
    evidence_paths = active.get('readiness_evidence', {})
    # Missing stages can be reported without traversing archived runtime
    # trees. Bind source/runtime only when there is stage evidence to admit.
    current_sources = source_manifest(root) if evidence_paths else None
    current_runtime = runtime_manifest() if evidence_paths else None
    for name, required in REQUIRED.items():
        def stage(name=name, required=required):
            if name not in evidence_paths:
                raise ValueError('Full-universe evidence not supplied: '+', '.join(required))
            path = root/evidence_paths[name]
            verify(path)
            report = json.loads((path/'report.json').read_text())
            binding = json.loads((path/'binding.json').read_text())
            if report.get('schema') != 'v7-full-universe-evidence-v1' or report.get('stage') != name:
                raise ValueError('Wrong evidence kind; component pilots are insufficient')
            if report.get('scope_identity') != scope:
                raise ValueError('Evidence belongs to another date/input/row contract')
            if (binding.get('sources') != current_sources or binding.get('runtime') != current_runtime
                    or binding.get('source_and_input_guard') != 'passed'):
                raise ValueError('Evidence source/runtime binding is stale or incomplete')
            for filename, digest in binding.get('inputs', {}).items():
                if sha(root/filename) != digest:
                    raise ValueError('Transitive evidence input changed')
            if not binding.get('inputs'):
                raise ValueError('No evidence inputs bound')
            if (universe is None or report.get('symbols') != sorted(set(universe[universe.month >= '2022-02'].ticker))
                    or report.get('security_ids') != sorted(set(universe[universe.month >= '2022-02'].security_id))):
                raise ValueError('Evidence does not cover the complete historical universe')
            failed = [key for key in required if report.get('checks', {}).get(key) is not True]
            if failed or report.get('limitations') != []:
                raise ValueError('Unpassed stage checks or limitations: '+', '.join(failed))
            return {'receipt_sha256': sha(path/'complete.json'), 'checks': list(required)}
        check(name, stage)
    return {'schema': 'v7-readiness-report-v1', 'scope_identity': scope,
            'ready_for_training': all(g['passed'] for g in gates), 'gates': gates,
            'full_launch_performed': False}
