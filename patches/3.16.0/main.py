"""
Patch 3.16.0 - MongoDB schema migrations.

Changes applied:
- Algorithm: unset the removed `ignore_actions` field from
  `recommendation_settings`.

The patch is idempotent: only documents that still contain the field are
touched.

Inside the K8S job the connection is built from the same envs the service uses:
r8s_mongo_user, r8s_mongo_password, r8s_mongo_url (host:port), r8s_mongo_db_name

Local usage:
    python3 main.py --uri mongodb://user:pass@host:27017/dbname [--dry-run]
"""

import argparse
import logging
import os
import sys
from urllib.parse import urlparse

import pymongo

logging.basicConfig(
    format='%(asctime)s %(levelname)s %(name)s.%(funcName)s:%(lineno)d '
           '%(message)s',
    level=logging.INFO,
)
_LOG = logging.getLogger(__name__)

ENV_MONGO_USER = 'r8s_mongo_user'
ENV_MONGO_PASSWORD = 'r8s_mongo_password'
ENV_MONGO_URL = 'r8s_mongo_url'
ENV_MONGO_DB_NAME = 'r8s_mongo_db_name'


def connect(uri: str | None) -> tuple[pymongo.MongoClient, str]:
    """Returns the client and the name of the database to patch."""
    if uri:
        db_name = urlparse(uri).path.lstrip('/')
        if not db_name:
            raise ValueError(
                'Database name must be specified in the URI path '
                '(e.g. mongodb://host:27017/mydb)'
            )
        return pymongo.MongoClient(uri), db_name

    envs = {
        name: os.environ.get(name)
        for name in (ENV_MONGO_USER, ENV_MONGO_PASSWORD, ENV_MONGO_URL,
                     ENV_MONGO_DB_NAME)
    }
    missing = [name for name, value in envs.items() if not value]
    if missing:
        raise ValueError(
            f'Specify --uri or set envs: {", ".join(missing)}'
        )
    host, _, port = envs[ENV_MONGO_URL].partition(':')
    # credentials are passed as kwargs to avoid URI escaping issues
    client = pymongo.MongoClient(
        host=host,
        port=int(port or 27017),
        username=envs[ENV_MONGO_USER],
        password=envs[ENV_MONGO_PASSWORD],
    )
    return client, envs[ENV_MONGO_DB_NAME]


def patch_algorithms(db, dry_run: bool) -> None:
    """Remove the obsolete recommendation settings field."""
    collection = db['algorithm']
    query = {'recommendation_settings.ignore_actions': {'$exists': True}}
    total = collection.count_documents({})
    matching = collection.count_documents(query)

    _LOG.info(f'[algorithms] Total documents: {total}')
    _LOG.info(f'[algorithms] with obsolete `ignore_actions` field: {matching}')

    if dry_run:
        _LOG.info('[algorithms] Dry run - skipping writes.')
        return

    if matching:
        result = collection.update_many(
            query,
            {'$unset': {'recommendation_settings.ignore_actions': ''}}
        )
        _LOG.info(f'[algorithms] Unset ignore_actions: '
                  f'{result.modified_count} documents.')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='r8s 3.16.0 patch')
    parser.add_argument(
        '--uri',
        help='MongoDB connection URI with the database name '
             '(e.g. mongodb://user:pass@host:27017/dbname). '
             'If omitted, connection is built from envs'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print counts without writing to the database'
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        client, db_name = connect(args.uri)
        _LOG.info(f'Patch 3.16.0 | db={db_name} | '
                  f'mode={"DRY-RUN" if args.dry_run else "APPLY"}')
        # fails fast if mongo is not reachable; the K8S job retries
        client.admin.command('ping')
        patch_algorithms(db=client[db_name], dry_run=args.dry_run)
        client.close()
        _LOG.info('Done.')
        return 0
    except Exception as e:
        _LOG.exception(f'Unexpected exception during patch: {e}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
