# Patch 3.16 - Remove `ignore_actions` from algorithms

## Purpose

The `ignore_actions` recommendation setting was removed in r8s 3.16. Algorithm
documents that still contain `recommendation_settings.ignore_actions` cannot
be loaded by the `Algorithm` model anymore. This patch unsets the field in
every document of the `algorithm` collection that still contains it.

- The patch is safe to run more than once: only documents that still contain the field are updated.
- The patch waits for MongoDB to become available before migrating.

## Configuration

The patch reuses the r8s source code (`src/`), so MongoDB connection settings
are resolved by `models` exactly as in the r8s services:

1. `r8s_mongodb_connection_uri` environment variable;
2. `r8s_mongo_user`, `r8s_mongo_password`, `r8s_mongo_url` (`host:port`) and
   `r8s_mongo_db_name` environment variables, as set by the `rightsizer` Helm
   chart;
3. `r8s_mongodb_connection_uri` secret from Vault (`VAULT_TOKEN`,
   `VAULT_URL`, `VAULT_SERVICE_SERVICE_PORT`).

| Argument           | Description                                              |
|:-------------------|:---------------------------------------------------------|
| `--dry-run`        | Count matching documents without changing them           |
| `--wait-timeout`   | Maximum MongoDB readiness wait in seconds, default `300` |
| `--retry-interval` | Seconds between MongoDB readiness checks, default `5`    |

Each readiness check can take up to 30 seconds (the default MongoDB server
selection timeout) before the next retry.

The patch exits with code `0` on success and `1` if the connection or the
migration fails.

## Building

The patch requires the r8s source code. Build from the repository root:

```bash
export PATCH_VERSION=3.16

# For AMD64
podman build --platform linux/amd64 \
  -t public.ecr.aws/x4s4z8e1/syndicate/patches:r8s-${PATCH_VERSION}-amd64 \
  -f ./scripts/patch/${PATCH_VERSION}/Dockerfile .

# For ARM64
podman build --platform linux/arm64 \
  -t public.ecr.aws/x4s4z8e1/syndicate/patches:r8s-${PATCH_VERSION}-arm64 \
  -f ./scripts/patch/${PATCH_VERSION}/Dockerfile .
```

## Running locally

Run from the repository root with `src` on `PYTHONPATH`:

```bash
export PYTHONPATH="$PWD/src"
export r8s_mongodb_connection_uri="mongodb://user:password@localhost:27017/r8s"
python scripts/patch/3.16/main.py --dry-run
python scripts/patch/3.16/main.py
```

Windows PowerShell:

```powershell
$env:PYTHONPATH = "$PWD\src"
$env:r8s_mongodb_connection_uri = "mongodb://user:password@localhost:27017/r8s"
python .\scripts\patch\3.16\main.py --dry-run
python .\scripts\patch\3.16\main.py
```
