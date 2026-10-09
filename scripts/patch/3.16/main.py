#!/usr/bin/env python3
"""Remove the obsolete ``ignore_actions`` field from Algorithm documents."""

import argparse
import sys
import time

from mongoengine import get_connection
from pymongo.errors import ServerSelectionTimeoutError

from commons.log_helper import get_logger

_LOG = get_logger('r8s-patch-3.16')

FIELD = 'recommendation_settings.ignore_actions'

DEFAULT_WAIT_TIMEOUT = 120
DEFAULT_RETRY_INTERVAL = 10


def wait_for_mongo(wait_timeout: int, retry_interval: int) -> None:
    deadline = time.monotonic() + wait_timeout
    while True:
        try:
            get_connection().admin.command('ping')
            _LOG.info('MongoDB is ready')
            return
        except ServerSelectionTimeoutError as error:
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f'MongoDB did not become ready within {wait_timeout} '
                    f'seconds'
                ) from error
            _LOG.info(f'MongoDB is not ready, retrying in {retry_interval} '
                      f'seconds')
            time.sleep(retry_interval)


def patch_algorithms(dry_run: bool) -> None:
    from models.algorithm import Algorithm

    # Raw queries: the field no longer exists in RecommendationSettings, so
    # documents that still contain it cannot be loaded through the model.
    queryset = Algorithm.objects(__raw__={FIELD: {'$exists': True}})
    matching = queryset.count()

    _LOG.info(f'Algorithms with obsolete {FIELD}: {matching}')
    if dry_run:
        _LOG.info('Dry run: no documents were changed')
        return
    if not matching:
        _LOG.info('No migration required')
        return

    updated = queryset.update(__raw__={'$unset': {FIELD: ''}})
    _LOG.info(f'Unset {FIELD} in {updated} document(s)')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='r8s 3.16 patch: remove obsolete ignore_actions field '
                    'from algorithms'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Count matching documents without writing changes',
    )
    parser.add_argument(
        '--wait-timeout',
        type=int,
        default=DEFAULT_WAIT_TIMEOUT,
        help=f'Maximum MongoDB readiness wait in seconds '
             f'(default: {DEFAULT_WAIT_TIMEOUT})',
    )
    parser.add_argument(
        '--retry-interval',
        type=int,
        default=DEFAULT_RETRY_INTERVAL,
        help=f'Seconds between MongoDB readiness checks '
             f'(default: {DEFAULT_RETRY_INTERVAL})',
    )
    args = parser.parse_args()
    if args.wait_timeout <= 0 or args.retry_interval <= 0:
        parser.error('--wait-timeout and --retry-interval must be positive')
    return args


def main() -> int:
    args = parse_args()

    _LOG.info('=' * 50)
    _LOG.info(f'Patch 3.16 | mode={"DRY-RUN" if args.dry_run else "APPLY"}')
    _LOG.info('=' * 50)

    try:
        import models  # noqa: F401  initializes the MongoDB connection
        wait_for_mongo(args.wait_timeout, args.retry_interval)
        patch_algorithms(dry_run=args.dry_run)
    except Exception as e:
        _LOG.exception(f'Patch failed: {e}')
        return 1

    _LOG.info('Patch 3.16 finished successfully')
    return 0


if __name__ == '__main__':
    sys.exit(main())
