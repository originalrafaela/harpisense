"""Explicit offline service writer; never dispatches actions or seeds production."""
import argparse
import json
import os
from pathlib import Path

from .core import Composition, DependencyBlocked
from .store import CompositionStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rf-directory', required=True)
    parser.add_argument('--rf-sha256', required=True)
    parser.add_argument('--if-directory', required=True)
    parser.add_argument('--if-sha256', required=True)
    parser.add_argument('--input', required=True, help='Explicit JSON window and service context')
    parser.add_argument('--input-origin', choices=['synthetic', 'p08'], required=True)
    parser.add_argument('--now', required=True, help='Evaluation time with timezone')
    parser.add_argument('--mode', type=int, choices=[1, 2, 3], default=1)
    parser.add_argument('--rf-reference', help='Installer-approved XAI background JSON')
    parser.add_argument('--if-reference', help='Installer-approved normal-training XAI background JSON')
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding='utf-8'))
    # Until the operational P08 gate opens, synthetic writes are confined to the
    # disposable test database. No candidate can contaminate the production P11.
    dsn = os.environ['DATABASE_URL']
    if args.input_origin == 'synthetic':
        from psycopg.conninfo import conninfo_to_dict
        if conninfo_to_dict(dsn).get('dbname') != 'detection_composition_test':
            parser.error('Synthetic composition requires detection_composition_test database')
    try:
        references = {name:json.loads(Path(path).read_text(encoding='utf-8')) for name,path in (
            ('random_forest',args.rf_reference),('isolation_forest',args.if_reference)) if path}
        composition = Composition(CompositionStore(dsn), rf_directory=args.rf_directory,
            rf_sha256=args.rf_sha256, if_directory=args.if_directory, if_sha256=args.if_sha256,
            xai_references=references)
        if args.input_origin == 'p08':
            result = composition.process_p08(**payload, now=args.now, mode=args.mode)
        else:
            result = composition.process_synthetic(**payload, now=args.now, mode=args.mode)
    except DependencyBlocked as exc:
        print(json.dumps(dict(status='BLOCKED', reasons=exc.reasons,
                              diagnostic=exc.diagnostic, execution_performed=False), ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
