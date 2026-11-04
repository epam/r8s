- a patch is a docker executable that will be executed as a K8S job (helm `pre-upgrade` hook, see `deployment/helm/rightsizer/templates/patch-job.yaml`)
- patch should not break the data if executed more than once
- patch executable has access to mongo credentials via `r8s_mongo_user`, `r8s_mongo_password`, `r8s_mongo_url`, `r8s_mongo_db_name` envs
- patch should wait till the patched service is started
- one directory per release version: `patches/<version>/{Dockerfile,main.py}`
- the job is enabled by `r8s-init update` (`patch.enabled=true`); pass `--no-patch` to skip it. If the upgrade fails, helm rolls back and the automatic backup is restored

## Building

Assuming that your working directory is `patches/`

Export the necessary patch version to env `PATCH_VERSION`:

```bash
export PATCH_VERSION=<specify version here>
```

Build for arm64:

```bash
podman build --platform linux/arm64 -t public.ecr.aws/x4s4z8e1/syndicate/patches:rightsizer-"$PATCH_VERSION"-arm64 -f ./"$PATCH_VERSION/Dockerfile" ./"$PATCH_VERSION"
```

Build for amd64:

```bash
podman build --platform linux/amd64 -t public.ecr.aws/x4s4z8e1/syndicate/patches:rightsizer-"$PATCH_VERSION"-amd64 -f ./"$PATCH_VERSION/Dockerfile" ./"$PATCH_VERSION"
```

Push both versions:

```bash
podman push public.ecr.aws/x4s4z8e1/syndicate/patches:rightsizer-"$PATCH_VERSION"-arm64
podman push public.ecr.aws/x4s4z8e1/syndicate/patches:rightsizer-"$PATCH_VERSION"-amd64
```

Create image manifest:

```bash
podman manifest rm public.ecr.aws/x4s4z8e1/syndicate/patches:rightsizer-"$PATCH_VERSION" || true
podman manifest create public.ecr.aws/x4s4z8e1/syndicate/patches:rightsizer-"$PATCH_VERSION" public.ecr.aws/x4s4z8e1/syndicate/patches:rightsizer-"$PATCH_VERSION"-arm64 public.ecr.aws/x4s4z8e1/syndicate/patches:rightsizer-"$PATCH_VERSION"-amd64
podman manifest annotate public.ecr.aws/x4s4z8e1/syndicate/patches:rightsizer-"$PATCH_VERSION" public.ecr.aws/x4s4z8e1/syndicate/patches:rightsizer-"$PATCH_VERSION"-arm64 --arch arm64
podman manifest annotate public.ecr.aws/x4s4z8e1/syndicate/patches:rightsizer-"$PATCH_VERSION" public.ecr.aws/x4s4z8e1/syndicate/patches:rightsizer-"$PATCH_VERSION"-amd64 --arch amd64
```

Push manifest:

```bash
podman manifest push public.ecr.aws/x4s4z8e1/syndicate/patches:rightsizer-"$PATCH_VERSION"
```

Then set `patch.image.tag` in the chart `values.yaml` to `rightsizer-<version>`.
