"""
Patch script for r8s 3.16.0 MongoDB schema migrations.

Changes applied:
- Algorithm: unset the removed `ignore_actions` field from
  `recommendation_settings`.

Only Algorithm documents that still contain the field are touched.

Usage:
    python3 mongodb_patch_remove_ignore_actions.py \
        --uri mongodb://user:pass@host:27017/dbname

    # Dry run (prints counts, no writes):
    python3 mongodb_patch_remove_ignore_actions.py \
        --uri mongodb://user:pass@host:27017/dbname --dry-run
"""

import argparse
from urllib.parse import urlparse

import pymongo


def patch_algorithms(db, dry_run: bool):
    """Remove the obsolete recommendation settings field."""
    collection = db['algorithm']
    total = collection.count_documents({})
    matching = collection.count_documents({
        'recommendation_settings.ignore_actions': {'$exists': True}
    })

    print(f'[algorithms] Total documents: {total}')
    print(f'[algorithms] with obsolete `ignore_actions` field: {matching}')

    if dry_run:
        print('[algorithms] Dry run — skipping writes.')
        return

    if matching:
        result = collection.update_many(
            {'recommendation_settings.ignore_actions': {'$exists': True}},
            {'$unset': {'recommendation_settings.ignore_actions': ''}}
        )
        print(f'[algorithms] Unset ignore_actions: '
              f'{result.modified_count} documents.')


def parse_args():
    parser = argparse.ArgumentParser(
        description='r8s 3.16.0 MongoDB ignore_actions patch'
    )
    parser.add_argument(
        '--uri',
        required=True,
        help='MongoDB connection URI '
             '(e.g. mongodb://user:pass@host:27017/dbname)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print counts without writing to the database'
    )
    return parser.parse_args()


def main():
    args = parse_args()

    parsed = urlparse(args.uri)
    db_name = parsed.path.lstrip('/')
    if not db_name:
        raise ValueError(
            'Database name must be specified in the URI path '
            '(e.g. mongodb://host:27017/mydb)'
        )

    print(f'Connecting to MongoDB (db={db_name})...')
    client = pymongo.MongoClient(args.uri)
    db = client[db_name]

    if args.dry_run:
        print('--- DRY RUN MODE ---')

    patch_algorithms(db=db, dry_run=args.dry_run)

    print('Done.')
    client.close()


if __name__ == '__main__':
    main()
