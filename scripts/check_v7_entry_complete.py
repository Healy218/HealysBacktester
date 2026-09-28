#!/usr/bin/env python3
"""systemd ExecCondition: defer research until the selected V7 download finishes."""
import argparse
import json
from pathlib import Path


def complete(path, campaign):
    try:
        receipt = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return False
    return isinstance(receipt, dict) and (
        receipt.get('campaign_identity') == campaign
        and receipt.get('status') == 'entry_capture_complete'
        and receipt.get('full_entry_coverage') is True
        and receipt.get('pending') == 0
        and 'stop_reason' in receipt
        and receipt['stop_reason'] is None
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--progress', type=Path, required=True)
    parser.add_argument('--campaign', required=True)
    args = parser.parse_args()
    if not complete(args.progress, args.campaign):
        print('V6 research deferred: selected V7 entry download is not complete.')
        raise SystemExit(1)
