"""Current V7 date scope; historical captures retain their original identities."""

HISTORY_START = '2022-03-15'
HISTORY_END = '2026-09-14'
EXCLUDED_START = '2022-03-08'
EXCLUDED_END = '2022-03-14'
EVALUATION_FILE = 'V7_EVALUATION_20220315_PHYSICAL.json'


def data_day_allowed(day):
    return not EXCLUDED_START <= day <= EXCLUDED_END and day <= HISTORY_END


def declaration():
    return {'history_start': HISTORY_START, 'history_end': HISTORY_END,
            'excluded_input_dates': [EXCLUDED_START, EXCLUDED_END],
            'warmup': 'Earlier captured history except excluded dates; no pre-start labels',
            'gap_policy': 'Keep exchange calendar; do not forward-fill deleted sessions',
            'evaluation_file': EVALUATION_FILE, 'research_ready': False}


def require_research_window(start, end):
    from datetime import date
    if (date.fromisoformat(start).isoformat() != start
            or date.fromisoformat(end).isoformat() != end
            or not HISTORY_START <= start <= end <= HISTORY_END):
        raise ValueError('Research window must lie inside the current V7 date scope')


def require_active_inputs(source):
    import json
    from pathlib import Path
    source = Path(source)
    if (json.loads((source/'scope.json').read_text()) != declaration()
            or json.loads((source/'report.json').read_text())['scope'] != declaration()):
        raise ValueError('Use completed working inputs for the current V7 scope')
