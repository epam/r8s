"""
Patch script for r8s 3.14.0 MongoDB schema migrations.

Changes applied:
- User:   set tenants=["*"], migrate role (str) -> roles ([str]), unset role
- Policy: set customer, tenants=[<tenant>], effect="allow"
- Role:   set customer, unset obsolete `resource` field

Only documents missing the new fields (or retaining old ones) are touched.
Requires MongoDB 4.2+ (uses aggregation pipeline updates for User migration).

Usage:
    python3 mongodb_patch_rbac.py \\
        --uri mongodb://user:pass@host:27017/dbname \\
        --customer CUSTOMER_NAME \\
        --tenant TENANT_NAME

    # Dry run (prints counts, no writes):
    python3 mongodb_patch_rbac.py --uri ... --customer ... --tenant ... --dry-run
"""

import argparse
from urllib.parse import urlparse

import pymongo
from mongoengine import DateTimeField, Document, ListField, StringField

class BaseModel(Document):
    meta = {'abstract': True}


class User(BaseModel):
    dto_skip_attrs = ['_id', 'password', 'latest_rt_version']

    user_id = StringField(required=True, unique=True)
    sub = StringField(unique=True)
    customer = StringField(null=True)
    role = StringField(null=True)
    password = StringField(null=True)
    latest_login = StringField(null=True)
    latest_rt_version = StringField(null=True)


class Policy(BaseModel):
    name = StringField(max_length=30, required=True, unique=True)
    permissions = ListField(StringField(null=True))


class Role(BaseModel):
    name = StringField(required=True, unique=True)
    expiration = DateTimeField(null=True)
    policies = ListField(StringField(null=True))
    resource = ListField(StringField(null=True))


def patch_users(db, dry_run: bool):
    """
    - Migrate role (string) -> roles ([string]), unset role
    - Set tenants = ["*"] where missing
    """
    collection = db['user']
    total = collection.count_documents({})
    print(f'[users] Total documents: {total}')

    has_role = collection.count_documents({'role': {'$exists': True}})
    missing_roles = collection.count_documents({'roles': {'$exists': False}})
    missing_tenants = collection.count_documents({'tenants': {'$exists': False}})
    print(f'[users]   with legacy `role` field:  {has_role}')
    print(f'[users]   missing `roles` field:     {missing_roles}')
    print(f'[users]   missing `tenants` field:   {missing_tenants}')

    if dry_run:
        print('[users] Dry run — skipping writes.')
        return

    if has_role:
        result = collection.update_many(
            {'role': {'$exists': True}},
            [
                {
                    '$set': {
                        'roles': {
                            '$cond': {
                                'if': {
                                    '$and': [
                                        {'$ne': ['$role', None]},
                                        {'$gt': ['$role', '']}
                                    ]
                                },
                                'then': ['$role'],
                                'else': []
                            }
                        }
                    }
                },
                {'$unset': ['role']}
            ]
        )
        print(f'[users] Migrated role -> roles: {result.modified_count} documents.')

    if missing_tenants:
        result = collection.update_many(
            {'tenants': {'$exists': False}},
            {'$set': {'tenants': ['*']}}
        )
        print(f'[users] Set tenants=[*]: {result.modified_count} documents.')


def patch_policies(db, customer: str, tenant: str, dry_run: bool):
    """
    Set customer, tenants=[<tenant>], effect="allow" only on Policy documents
    that are missing these fields.
    """
    collection = db['policy']
    total = collection.count_documents({})
    print(f'[policies] Total documents: {total}')

    missing_customer = collection.count_documents({'customer': {'$exists': False}})
    missing_tenants = collection.count_documents({'tenants': {'$exists': False}})
    missing_effect = collection.count_documents({'effect': {'$exists': False}})
    print(f'[policies]   missing `customer`: {missing_customer}')
    print(f'[policies]   missing `tenants`:  {missing_tenants}')
    print(f'[policies]   missing `effect`:   {missing_effect}')

    if dry_run:
        print('[policies] Dry run — skipping writes.')
        return

    if missing_customer:
        result = collection.update_many(
            {'customer': {'$exists': False}},
            {'$set': {'customer': customer}}
        )
        print(f'[policies] Set customer: {result.modified_count} documents.')

    if missing_tenants:
        result = collection.update_many(
            {'tenants': {'$exists': False}},
            {'$set': {'tenants': [tenant]}}
        )
        print(f'[policies] Set tenants: {result.modified_count} documents.')

    if missing_effect:
        result = collection.update_many(
            {'effect': {'$exists': False}},
            {'$set': {'effect': 'allow'}}
        )
        print(f'[policies] Set effect: {result.modified_count} documents.')


def patch_roles(db, customer: str, dry_run: bool):
    """
    Set customer where missing and unset the removed `resource` field.
    """
    collection = db['role']
    total = collection.count_documents({})
    print(f'[roles] Total documents: {total}')

    has_resource = collection.count_documents({'resource': {'$exists': True}})
    missing_customer = collection.count_documents({'customer': {'$exists': False}})
    print(f'[roles]   with obsolete `resource` field: {has_resource}')
    print(f'[roles]   missing `customer` field:       {missing_customer}')

    if dry_run:
        print('[roles] Dry run — skipping writes.')
        return

    if missing_customer:
        result = collection.update_many(
            {'customer': {'$exists': False}},
            {'$set': {'customer': customer}}
        )
        print(f'[roles] Set customer: {result.modified_count} documents.')

    if has_resource:
        result = collection.update_many(
            {'resource': {'$exists': True}},
            {'$unset': {'resource': ''}}
        )
        print(f'[roles] Unset resource: {result.modified_count} documents.')


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description='r8s 3.14.0 MongoDB RBAC patch'
    )
    parser.add_argument('--uri', required=True,
                        help='MongoDB connection URI '
                             '(e.g. mongodb://user:pass@host:27017/dbname)')
    parser.add_argument('--customer', required=True,
                        help='Customer name to assign to policies and roles')
    parser.add_argument('--tenant', required=True,
                        help='Tenant name to assign to policies')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print counts without writing to the database')
    return parser.parse_args()


def main():
    args = parse_args()

    parsed = urlparse(args.uri)
    db_name = parsed.path.lstrip('/')
    if not db_name:
        raise ValueError('Database name must be specified in the URI path '
                         '(e.g. mongodb://host:27017/mydb)')

    print(f'Connecting to MongoDB (db={db_name})...')
    client = pymongo.MongoClient(args.uri)
    db = client[db_name]

    if args.dry_run:
        print('--- DRY RUN MODE ---')

    patch_users(db=db, dry_run=args.dry_run)
    patch_policies(db=db, customer=args.customer, tenant=args.tenant,
                   dry_run=args.dry_run)
    patch_roles(db=db, customer=args.customer, dry_run=args.dry_run)

    print('Done.')
    client.close()


if __name__ == '__main__':
    main()
