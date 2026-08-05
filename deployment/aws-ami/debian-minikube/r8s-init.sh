#!/bin/bash

set -eo pipefail

cmd_usage() {
  cat <<EOF
Manage RightSizer installation

Usage:
  $PROGRAM [command]

Available Commands:
  backup   Allow to manage backups
  check    Alias for doctor
  doctor   Check local environment and CLI compatibility
  health   Check installation health
  help     Show help message
  init     Initialize RightSizer installation
  list     Lists available updates
  nginx    Allow to enable and disable nginx sites
  update   Update the installation
  version  Print versions information
EOF
}

cmd_init_usage() {
  cat <<-EOF
Initializes RightSizer

Description:
  Initializes RightSizer for the first time or for a specified user. Includes installing CLIs, configuring passwords and other

Usage:
  $PROGRAM $COMMAND [options]

Examples:
  $PROGRAM $COMMAND --system
  $PROGRAM $COMMAND --user example --public-ssh-key "ssh-rsa AAA..."

Options:
  -h, --help        Show this message and exit
  --system          Initialize R8S for the first time. Only possible for $FIRST_USER user. Creates necessary system entities
  --user            Initialize R8S for the given user
  --public-ssh-key  If specified will be added to user's authorized_keys.
  --r8s-username    RightSizer username to configure. Must be specified together with --r8s-password
  --r8s-password    RightSizer password to configure. Must be specified together with --r8s-username
  --admin-username  Modular Service username to configure. Must be specified together with --admin-password
  --admin-password  Modular Service password to configure. Must be specified together with --admin-username

Environment variables:
  R8S_PYTHON_BIN
      Optional Python interpreter used during CLI installation.
      If not set, r8s-init tries python3.14 first, then falls back to python3.
      Example: R8S_PYTHON_BIN=/usr/local/bin/python3.14 r8s-init init --user example
  R8S_PYTHON_COMPAT_MODE
      Compatibility behavior when Python requirement is not satisfied.
      Supported values: warn, error (default: error)
EOF
}

cmd_update_usage() {
  cat <<EOF
Updates local RightSizer Installation

Description:
  Checks for new release and performs update if it's available

Usage:
  $PROGRAM $COMMAND [options]

Examples:
  $PROGRAM $COMMAND --check
  $PROGRAM $COMMAND -y
  $PROGRAM $COMMAND -y --allow-prereleases

Options:
  -h, --help           Show this message and exit
  -y, --yes            Automatic yes to prompts
  --allow-prereleases  Include pre-release versions when checking for updates
  --check              Checks whether update is available but do not try to update
  --no-backup          Do not do backup before updating
  --same-version       Fetches artifacts for the version currently installed and reinstalls
  --defectdojo         Specify this flag to update Defect Dojo chart instead of RightSizer
  --helm-release-name  RightSizer helm release name (default "$HELM_RELEASE_NAME")
  --backup-name        Backup name to make before the update (default "$AUTO_BACKUP_PREFIX\$timestamp")
EOF
}
cmd_update_list_usage() {
  cat <<EOF
Displays available releases

Description:
  Lists available RightSizer releases. Uses GitHub rest api under the hood and
  can throttle if rate limit is exceeded

Usage:
  $PROGRAM $COMMAND [options]

Examples:
  $PROGRAM $COMMAND

Options:
  -h, --help           Show this message and exit
  --allow-prereleases  Include pre-release versions in the list
EOF
}

cmd_nginx_usage() {
  cat <<EOF
Manage existing nginx configurations for RightSizer

Description:
  Allows to enable and disable existing nginx configurations and corresponding k8s services. The command is not designed
  to be flexible. It just allows to enable and disable pre-defined services easily.

Examples:
  $PROGRAM $COMMAND ls
  $PROGRAM $COMMAND enable r8s
  $PROGRAM $COMMAND disable defectdojo

Available Commands:
  disable     Disable the given nginx server
  enable      Enable the given nginx server
  help        Show help message
  ls          Show available nginx servers

Options:
  -h, --help  Show this message and exit
EOF
}

cmd_backup_usage() {
  cat <<EOF
Manage local backups

Description:
  Command for managing local backups of persistent volumes from k8s

Examples:
  $PROGRAM $COMMAND

Available Command:
  create      Creates a new backup
  help        Show help message
  ls          Show created backups
  restore     Restores backup
  rm          Removes existing backup

Options
  -h, --help  Show helm message
EOF
}

cmd_backup_list_usage() {
  cat <<EOF
Shows local backups

Description:
  Command for describing all created backups

Examples:
  $PROGRAM $COMMAND ls

Options
  -h, --help     Show help message
  -v, --version  Version of RightSizer release for which backups where made (default current release "$(get_helm_release_version "$HELM_RELEASE_NAME")")
  -p, --path     Path where backups are store (default "$R8S_BACKUPS_PATH/\$version"). --version parameter is ignored when custom --path is specified
EOF
}
cmd_backup_rm_usage() {
  cat <<EOF
Removes local backup

Description:
  Command for removing local backup

Examples:
  $PROGRAM $COMMAND rm --name my-backup

Required Options:
  -n, --name     Backup name to remove

Options
  -h, --help     Show help message
  -y, --yes      Automatic yes to prompts
  -v, --version  Version of RightSizer release for which backups where made (default current release "$(get_helm_release_version "$HELM_RELEASE_NAME")")
  -p, --path     Path where backups are stored (default "$R8S_BACKUPS_PATH/\$version"). Note that --version parameter is ignored when custom --path is specified
EOF
}
cmd_backup_create_usage() {
  cat <<EOF
Creates local backup

Description:
  Command for creating local backup

Examples:
  $PROGRAM $COMMAND create --name my-backup
  $PROGRAM $COMMAND create --name my-backup --volumes=minio,mongo,vault

Required Options:
  -n, --name  Backup name to create

Options
  -h, --help  Show help message
  -p, --path  Path where backups are store (default "$R8S_BACKUPS_PATH/$(get_helm_release_version "$HELM_RELEASE_NAME")")
  --volumes   Volumes to make the backup for. Uses all k8s volumes if not specified. Specify volumes divided by comma
EOF
}

cmd_backup_restore_usage() {
  cat <<EOF
Restores local backup

Description:
  Command for restoring local backup

Examples:
  $PROGRAM $COMMAND restore --name my-backup
  $PROGRAM $COMMAND restore --name my-backup --volumes=minio,mongo,vault

Required Options:
  -n, --name     Backup name to create

Options
  -h, --help     Show help message
  -v, --version  Version of RightSizer release for which backups where made (default current release "$(get_helm_release_version "$HELM_RELEASE_NAME")")
  -p, --path     Path where backups are store (default "$R8S_BACKUPS_PATH/\$version"). --version parameter is ignored when custom --path is specified
  -f, --force    Restore backup even if current release version does not match to the release version where backup was made
  --volumes      Volumes to make the backup for. Uses all k8s volumes if not specified. Specify volumes divided by comma
EOF
}
cmd_health_usage() {
  cat <<EOF
Checks installation health

Description:
  Command that verifies different aspects of installation. Returns 1 in case something is wrong

Examples:
  $PROGRAM $COMMAND

Options
  -h, --help  Show this message and exit
EOF
}
cmd_doctor_usage() {
  cat <<EOF
Usage:
  $PROGRAM doctor [OPTIONS]
  $PROGRAM check [OPTIONS]

Checks local environment and RightSizer CLI installation compatibility.

Options:
  --release <version>    Check compatibility against a specific local release
  -h, --help             Show this help message

Environment variables:
  R8S_PYTHON_BIN         Optional Python interpreter used to install RightSizer CLI applications.
  R8S_PYTHON_COMPAT_MODE Compatibility behavior when Python requirement is not satisfied.
                         Supported values: warn, error
EOF
}


cmd_version() { echo "$VERSION"; }
die() { echo "Error:" "$@" >&2; exit 1; }
die_with_support() {
  echo "Error:" "$@" >&2
  echo "Please contact our support team at $SUPPORT_EMAIL for further assistance." >&2
  exit 1
}
warn() { echo "Warning:" "$@" >&2; }
_debug() {
  [ -z "$R8S_INIT_DEBUG" ] && return 0
  echo "Debug:" "$@" >&2
}
cmd_unrecognized() {
  cat <<EOF
Error: unrecognized command \`$PROGRAM $COMMAND\`
Try '$PROGRAM --help' for more information
EOF
}


# helper functions
get_latest_local_release() { ls "$R8S_RELEASES_PATH" | sort -Vr | head -n 1; }
get_helm_release_version() {
  # currently the version of rightsizer chart corresponds to the version of app inside
  helm get metadata "$1" -o json 2>/dev/null | jq -r '.version'
}
github_api_get() {
  # Retries on GitHub rate-limit (HTTP 429/403) with exponential back-off; prints body to stdout
  local attempt max_attempts=4 wait=5 http_code tmp
  tmp="$(mktemp)"
  for attempt in $(seq 1 "$max_attempts"); do
    http_code=$(curl -Ls -w '%{http_code}' -o "$tmp" "$@")
    if [ "$http_code" -eq 200 ]; then
      cat "$tmp"; rm -f "$tmp"; return 0
    fi
    if [ "$attempt" -lt "$max_attempts" ] && { [ "$http_code" -eq 429 ] || [ "$http_code" -eq 403 ]; }; then
      warn "GitHub API throttled (HTTP $http_code); retrying in ${wait}s (attempt $attempt/$max_attempts)..."
      sleep "$wait"
      wait=$((wait * 2))
    else
      rm -f "$tmp"; return 1
    fi
  done
  rm -f "$tmp"; return 1
}
iter_github_releases() {
  # iterates only over released versions by default. --prerelease flag includes pre-releases to output. --draft includes drafts
  local opts draft=0 prerelease=0 per_page=${GITHUB_PER_PAGE:-30} filter
  opts="$(getopt -o "" --long "draft,prerelease,per-page:," -n iter_github_releases -- "$@")"
  eval set -- "$opts"
  while true; do
    case "$1" in
      --draft) draft=1; shift ;;
      --prerelease) prerelease=1; shift ;;
      --per-page) per_page="$2"; shift 2 ;;
      '--') shift; break ;;
    esac
  done
  if [ "$draft" -eq 1 ] && [ "$prerelease" -eq 1 ]; then
    filter='.[]'
  elif [ "$draft" -eq 0 ] && [ "$prerelease" -eq 1 ]; then
    filter='.[] | select(.draft == false)'
  elif [ "$draft" -eq 1 ] && [ "$prerelease" -eq 0 ]; then
    filter='.[] | select(.prerelease == false)'
  else
    filter='.[] | select(.prerelease == false and .draft == false)'
  fi
  github_api_get -H 'Accept: application/vnd.github+json' "${GITHUB_CURL_HEADERS[@]}" "https://api.github.com/repos/$GITHUB_REPO/releases?per_page=$per_page" | jq -c "$filter" || die "Could not make request to GitHub. Probably rate limit exceeded"
}
get_github_release_by_tag() {
  local tag_name
  while IFS= read -r item; do
    tag_name=$(jq -r '.tag_name' <<<"$item")
    if [ "$1" = "$tag_name" ]; then
      echo "$item"
      return
    fi
  done < <(iter_github_releases --prerelease --draft)
  return 1
}
get_new_github_release() {
  # requires one parameter -> current release
  local current_release="$1" tag_name result
  shift # all other parameters are passed to iter_github_releases

  while IFS= read -r item; do
    tag_name=$(jq -r '.tag_name' <<<"$item")
    if dpkg --compare-versions "$tag_name" gt "$current_release"; then
      result="$item"
    elif [ -n "$result" ]; then
      echo "$result"
      return 0
    else
      break
    fi
  done < <(iter_github_releases "$@")
  return 1
}
get_release_type() {
  if [ "$(jq '.draft' <<<"$1")" = 'true' ]; then
    echo 'draft'
  elif [ "$(jq '.prerelease' <<<"$1")" = 'true' ]; then
    echo 'prerelease'
  else
    echo 'release'
  fi
}
colorize() {
  local color
  case "$1" in
    GREEN) color="\033[32m" ;;
    RED) color="\033[31m" ;;
    YELLOW) color="\033[33m" ;;
    *) color="" ;;
  esac
  printf "%b" "$color"
  cat -
  printf "\033[0m"
}
check_asset_digest() {
  # accepts path to file and asset json
  local digest
  if [ ! -f "$1" ]; then
    return 1
  fi
  digest="$(jq -r '.digest' <<<"$2" | sed 's/^sha256://')"
  if [ "$(sha256sum "$1" | awk '{print $1}')" != "$digest" ]; then
    return 1
  fi
}
download_from_github_url() {
  # accepts two parameters: destination path and url
  local tmp_file
  tmp_file="$(mktemp -t r8s-init.XXXXXX)"

  if curl -fLs "${GITHUB_CURL_HEADERS[@]}" -o "$tmp_file" -H "Accept: application/octet-stream" "$2"; then
    mv "$tmp_file" "$1"
    return 0
  else
    rm -f "$tmp_file"
    return 1
  fi
}
pull_artifact() {
  # accepts two parameters: destination folder and github's asset json
  local name destination url

  name="$(jq -r '.name' <<<"$2")"
  destination="$1/$name"

  if [ -f "$destination" ]; then
    if check_asset_digest "$destination" "$2"; then
      _debug "asset $name is up-to-date, skipping download"
      return 0
    fi
  fi

  url="$(jq -r '.url' <<<"$2")"
  if download_from_github_url "$destination" "$url"; then
    echo "Downloaded $name"
    return 0
  else
    warn "Could not download $name"
    return 1
  fi
}
find_asset_by_name() {
  # accepts release data returned by github api and asset name. Returns asset json if found
  local asset
  asset="$(jq --arg name "$2" '.assets[] | select(.name == $name)' <<<"$1")"
  if [ -z "$asset" ]; then
    return 1
  fi
  echo "$asset"
}
ensure_in_path() {
  if [[ ":$PATH:" != *":$1:"* ]]; then
    export PATH=$PATH:$1
  fi
}
# shellcheck disable=SC2120
generate_password() {
  chars="20"
  typ='-base64'
  if [ -n "$1" ]; then
    chars="$1"
  fi
  if [ -n "$2" ]; then
    typ="$2"
  fi
  openssl rand "$typ" "$chars"
}
get_imds_token () {
  curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 20"
}
account_id() { curl -s curl -s -H "X-aws-ec2-metadata-token: $(get_imds_token)" http://169.254.169.254/latest/dynamic/instance-identity/document | jq -r ".accountId"; }
user_exists() { id "$1" &>/dev/null; }
get_kubectl_secret() {
  kubectl get secret "$1" -o jsonpath="{.data.$2}" | base64 --decode
}
minikube_ip(){
  # user may exist in docker group but re-login wasn't made
  sudo su "$FIRST_USER" -c "minikube ip"
}
yesno() {
	[[ -t 0 ]] || return 0
	local response
	read -r -p "$1 [y/N] " response
	[[ $response == [yY] ]] || exit 1
}
patch_kubectl_secret() {
  local secret
  secret=$(base64 <<< "$3")
  kubectl patch secret "$1" -p="{\"data\":{\"$2\":\"$secret\"}}"
}
update_modular_api_policy() {
  modular_api_pod_name=$(kubectl get pods -n default -l app.kubernetes.io/name=modular-api -o jsonpath='{.items[0].metadata.name}')
  echo $MODULAR_ADMIN_POLICY > /tmp/modular-admin-policy.json
  kubectl cp /tmp/modular-admin-policy.json $modular_api_pod_name:/src/admin_policy.json
  kubectl exec service/modular-api -- ./modular.py policy update --policy admin_policy --policy_path /src/admin_policy.json
  rm /tmp/modular-admin-policy.json
}

build_multiple_params() {
  # build_multiple_params --email "admin@gmail.com admin2@gmail.com" -> --email admin@gmail.com --email admin2gmail.com
  local item counter=0
  for item in $2; do
    if [ -n "$3" ] && [ "$counter" -eq "$3" ]; then return; fi
    [ -z "$item" ] && continue
    printf "%s %s " "$1" "$item"
    ((counter++))
  done
}

resolve_customer_name() {
  # used only if license activation is disabled
  if [ -n "$CUSTOMER_NAME" ]; then
    echo "$CUSTOMER_NAME"
  else
    echo CUSTOMER_1
  fi
}
resolve_python_bin() {
  if [ -n "$R8S_PYTHON_BIN" ]; then
    if command -v "$R8S_PYTHON_BIN" >/dev/null 2>&1; then
      command -v "$R8S_PYTHON_BIN"
      return 0
    fi
    if [ -x "$R8S_PYTHON_BIN" ]; then
      echo "$R8S_PYTHON_BIN"
      return 0
    fi
    die "Requested Python interpreter '$R8S_PYTHON_BIN' was not found or is not executable"
  fi
  for candidate in python3.14 /usr/local/bin/python3.14 /opt/python/3.14/bin/python3.14; do
    if command -v "$candidate" >/dev/null 2>&1; then
      command -v "$candidate"
      return 0
    fi
    if [ -x "$candidate" ]; then
      echo "$candidate"
      return 0
    fi
  done
  command -v python3 || die "python3 was not found"
}
python_version() {
  "$1" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'
}
python_satisfies() {
  "$1" - "$2" <<'PY'
import sys
required = tuple(map(int, sys.argv[1].split(".")[:2]))
current = sys.version_info[:2]
sys.exit(0 if current >= required else 1)
PY
}
release_metadata_path() {
  echo "$R8S_RELEASES_PATH/$1/$R8S_RELEASE_METADATA_NAME"
}
release_metadata_exists() {
  [ -f "$(release_metadata_path "$1")" ]
}
get_release_metadata_value() {
  local metadata_file
  metadata_file="$(release_metadata_path "$1")"
  [ -f "$metadata_file" ] || return 1
  jq -er "$2" "$metadata_file" 2>/dev/null
}
get_modular_cli_min_python() {
  if ! release_metadata_exists "$1"; then
    echo "${R8S_LEGACY_MODULAR_CLI_MIN_PYTHON:-3.10}"
    return 0
  fi
  get_release_metadata_value "$1" '.components.modular_cli.python_min_version' \
    || echo "$R8S_DEFAULT_MODULAR_CLI_MIN_PYTHON"
}
get_modular_cli_compat_mode() {
  if ! release_metadata_exists "$1"; then
    echo "${R8S_LEGACY_PYTHON_COMPAT_MODE:-warn}"
    return 0
  fi
  get_release_metadata_value "$1" '.components.modular_cli.compatibility_mode' \
    || echo "$R8S_PYTHON_COMPAT_MODE"
}
get_modular_cli_compat_message() {
  if ! release_metadata_exists "$1"; then
    echo "Legacy release metadata is missing. Using backward-compatible Python requirements."
    return 0
  fi
  get_release_metadata_value "$1" '.components.modular_cli.message' \
    || echo "Modular CLI requires Python $(get_modular_cli_min_python "$1") or later."
}
check_modular_cli_python_compatibility() {
  # prints resolved python_bin to stdout; warns/errors if version unsatisfied
  local release="$1"
  local python_bin required_version current_version compat_mode message

  python_bin="$(resolve_python_bin)"
  required_version="$(get_modular_cli_min_python "$release")"
  current_version="$(python_version "$python_bin")"
  compat_mode="$(get_modular_cli_compat_mode "$release")"
  message="$(get_modular_cli_compat_message "$release")"

  if python_satisfies "$python_bin" "$required_version"; then
    echo "$python_bin"
    return 0
  fi

  cat >&2 <<EOF
Warning: Python compatibility change detected.

$message

Required: Python $required_version or later
Detected: Python $current_version
Interpreter: $python_bin

To avoid installation or update failures, install Python $required_version+ and explicitly pass it:

  R8S_PYTHON_BIN=/usr/local/bin/python${required_version} r8s-init ...

Do not replace the system default /usr/bin/python3, as it may break OS-level tools.
EOF

  if [ "$compat_mode" = "warn" ]; then
    echo "$python_bin"
    return 0
  fi

  if [ -t 0 ]; then
    yesno "Continue anyway?"
    echo "$python_bin"
    return 0
  fi

  die "Unsupported Python version for Modular CLI installation"
}
pip_install_artifact() {
  # $1=python_bin $2=artifact_path; remaining args forwarded to pip (e.g. --upgrade)
  local python_bin="$1" artifact_path="$2"
  shift 2
  echo "Installing '$(basename "$artifact_path")' using Python interpreter: $python_bin"
  MODULAR_CLI_ENTRY_POINT=$MODULAR_CLI_ENTRY_POINT "$python_bin" -m pip install --user --break-system-packages "$@" "$artifact_path"
}
validate_cli_artifacts() {
  local release_path="$R8S_RELEASES_PATH/$1"
  [ -f "$release_path/$MODULAR_CLI_ARTIFACT_NAME" ] \
    || die_with_support "Modular CLI artifact was not found: $release_path/$MODULAR_CLI_ARTIFACT_NAME"
}

initialize_system() {
  # creates:
  # - non-system admin users for RightSizer & Modular Service
  # - license entity based on LM response
  # - customer based on LM response
  # - tenant within the customer which represents this AWS account
  # - entity that represents defect dojo installation
  local mip lm_response customer_name modular_service_password rightsizer_password license_key dojo_token="" activation_id
  mip="$(minikube_ip)"

  ensure_in_path "$HOME/.local/bin"
  sleep 5m # todo temporary
  local latest_release python_bin
  latest_release="$(get_latest_local_release)"
  validate_cli_artifacts "$latest_release"
  python_bin="$(check_modular_cli_python_compatibility "$latest_release")"
#  echo "Installing obfuscation manager"
#  pip_install_artifact "$python_bin" "$R8S_RELEASES_PATH/$latest_release/${OBFUSCATOR_ARTIFACT_NAME}[xlsx]" --upgrade
  echo "Installing modular-cli"
  pip_install_artifact "$python_bin" "$R8S_RELEASES_PATH/$latest_release/$MODULAR_CLI_ARTIFACT_NAME" --upgrade

  echo "Updating modular admin policy"
  update_modular_api_policy
  echo "Modular API policy has been updated."

  echo "Logging in to modular-cli"
  syndicate setup --username admin --password "$(get_kubectl_secret modular-api-secret system-password)" --api_path "http://$mip:32105" --json
  syndicate login --json

  echo "Logging in to RightSizer using system user"
  syndicate r8s configure --api_link http://rightsizer:8000/r8s --json
  syndicate r8s login --username SYSTEM_ADMIN --password "$(get_kubectl_secret rightsizer-secret system-password)" --json

  echo "Logging in to Modular Service using system user"
  syndicate admin configure --api_link http://modular-service:8040/dev --json
  syndicate admin login --username system_user --password "$(get_kubectl_secret modular-service-secret system-password)" --json

  echo "Generating passwords for modular-service and rightsizer non-system users"
  modular_service_password="$(generate_password)"
  rightsizer_password="$(generate_password)"
  patch_kubectl_secret "$RIGHTSIZER_SECRET_NAME" "admin-password" "$rightsizer_password"
  patch_kubectl_secret "$MODULAR_SERVICE_SECRET_NAME" "admin-password" "$modular_service_password"

  if [ -z "$DO_NOT_ACTIVATE_LICENSE" ]; then
    customer_name="$(jq ".customer_name" -r <<<"$(get_kubectl_secret lm-data lm-response)")"
    lm_response="$(get_kubectl_secret lm-data lm-response)"
  else
    customer_name="$(resolve_customer_name)"
  fi
  # here i must create customer if it does not exit
  if ! syndicate admin customer describe --name "$customer_name" >/dev/null 2>&1; then
    echo "Creating customer $customer_name"
    syndicate admin customer add --name "$customer_name" --display_name "$customer_name" $(build_multiple_params --admin "$ADMIN_EMAILS") --json
  fi

  echo "Creating modular service policy, role and user"
  syndicate admin policy add --name admin_policy --permissions_admin --customer_id "$customer_name" --json
  syndicate admin role add --name admin_role --policies admin_policy --customer_id "$customer_name" --json
  syndicate admin users create --username "$MODULAR_SERVICE_USERNAME" --password "$modular_service_password" --role_name admin_role --customer_id "$customer_name" --json

  echo "Creating rightsizer lm setting"
  LM_API_LINK=$(get_kubectl_secret lm-data api-link)
  syndicate r8s setting config add --host $LM_API_LINK --port 443 --protocol "HTTPS" --stage '/' --json

  if [ -z "$DO_NOT_ACTIVATE_LICENSE" ]; then
    echo "Creating rightsizer lm client"
    syndicate r8s setting client add --key_id "$(echo "$lm_response" | jq ".private_key.key_id" -r)" --algorithm "$(echo "$lm_response" | jq ".private_key.algorithm" -r)" --private_key "$(echo "$lm_response" | jq ".private_key.value" -r)" --format "PEM" --b64encoded --json
  fi

  echo "Creating rightsizer customer users"
  syndicate r8s register --username "$RIGHTSIZER_USERNAME" --password "$rightsizer_password" --role_name admin_role --customer_id "$customer_name" --json

  echo "Logging in as customer users"
  syndicate admin login --username "$MODULAR_SERVICE_USERNAME" --password "$modular_service_password" --json
  syndicate r8s login --username "$RIGHTSIZER_USERNAME" --password "$rightsizer_password" --json

  if [ -z "$DO_NOT_ACTIVATE_TENANT" ]; then
    echo "Activating tenant for the current aws account"
    syndicate admin tenant create --name "$CURRENT_ACCOUNT_TENANT_NAME" --display_name "Tenant $(account_id)" --cloud AWS --account_id "$(account_id)" --primary_contacts admin@example.com --secondary_contacts admin@example.com --tenant_manager_contacts admin@example.com --default_owner admin@example.com --json

    echo "Activating region for tenant"
    for r in $AWS_REGIONS;
    do
      echo "Activating $r for tenant"
      syndicate admin tenant regions activate --tenant_name "$CURRENT_ACCOUNT_TENANT_NAME" --region_name "$r" --json > /dev/null
    done
  fi

  if [ -z "$DO_NOT_ACTIVATE_LICENSE" ]; then
    echo "Setting up RightSizer Licensed Application"
    output=$(syndicate r8s application licenses add --customer_id "$customer_name" --description "$customer_name application" --cloud "AWS" --tenant_license_key "$(echo "$lm_response" | jq ".tenant_license_key" -r)" --json)
    licensed_application_id=$(echo "$output" | jq ".items[0].application_id" -r)

    echo "Setting up Licensed Parent"
    syndicate r8s parent add --application_id "$licensed_application_id" --description "$customer_name parent" --scope "SPECIFIC" --tenant "$CURRENT_ACCOUNT_TENANT_NAME" --json
  fi


  if [ -z "$DO_NOT_ACTIVATE_STORAGE" ]; then
    echo "Setting up Metrics storage"
    syndicate r8s storage add --storage_name input_storage --type DATA_SOURCE --bucket_name r8s-metrics --json

    echo "Setting up Scan results storage"
    syndicate r8s storage add --storage_name output_storage --type STORAGE --bucket_name r8s-results --json

    echo "Setting up RIGHTSIZER Application"
    syndicate r8s application add --customer_id "$customer_name" --description "$customer_name application" --input_storage input_storage --output_storage output_storage --username "ADMIN" --password "ADMIN" --host "0.0.0.0" --port 8000 --protocol HTTP --json
  fi

  echo "Getting Defect dojo token"
  while [ -z "$dojo_token" ]; do
    sleep 2
    dojo_token=$(curl -X POST -H 'content-type: application/json' "http://$mip:32107/api/v2/api-token-auth/" -d "{\"username\":\"admin\",\"password\":\"$(get_kubectl_secret "$DEFECTDOJO_SECRET_NAME" system-password)\"}" | jq ".token" -r || true)
  done

  echo "Activating dojo installation for rightsizer"

  echo "Creating RightSizer Dojo Application"
  output=$(syndicate r8s application dojo add --customer_id "$customer_name" --description "$customer_name Dojo Application" --host "$mip" --port "32107" --protocol "HTTP" --stage "api/v2" --api_key "$dojo_token" --json)
  dojo_application_id=$(echo "$output" | jq ".items[0].application_id" -r)

  echo "Creating RightSizer Dojo Parent for application $dojo_application_id"
  syndicate r8s parent dojo add --application_id "$dojo_application_id" --description "$customer_name Dojo parent" --tenant "$CURRENT_ACCOUNT_TENANT_NAME" --scope "SPECIFIC" --json

}

cmd_init() {
  local opts init_system="" target_user="" public_ssh_key="" r8s_username="" r8s_password="" admin_username="" admin_password="" new_password api_path
  opts="$(getopt -o "h" --long "help,system,user:,public-ssh-key:,r8s-username:,r8s-password:,admin-username:,admin-password:" -n "$PROGRAM" -- "$@")"
  eval set -- "$opts"
  while true; do
    case "$1" in
      '-h'|'--help') cmd_init_usage; exit 0 ;;
      '--system') init_system="true"; shift ;;
      '--user') target_user="$2"; shift 2 ;;
      '--public-ssh-key') public_ssh_key="$2"; shift 2 ;;
      '--r8s-username') r8s_username="$2"; shift 2 ;;
      '--r8s-password') r8s_password="$2"; shift 2 ;;
      '--admin-username') admin_username="$2"; shift 2 ;;
      '--admin-password') admin_password="$2"; shift 2 ;;
      '--') shift; break ;;
    esac
  done

  if [ -z "$init_system" ] && [ -z "$target_user" ]; then
    die "either --system or --user must be specified"
  fi

  if [ -n "$init_system" ]; then
    if [ "$FIRST_USER" != "$(whoami)" ]; then
      die "system configuration can be performed only by '$FIRST_USER' user"
    fi
    if [ -f "$R8S_LOCAL_PATH/success" ]; then
      die "RightSizer was already initialized. Cannot do that again"
    fi
    echo "Initializing RightSizer for the first time"
    initialize_system
    echo "Done"
    return
  fi

  # target_user must exist here
  local _username=1 _password=1
  [ -n "$r8s_username" ] && _username=0
  [ -n "$r8s_password" ] && _password=0
  if [ "$(( _username ^ _password ))" -eq 1 ]; then
    die "--r8s-username and --r8s-password must be specified together"
  fi

  _username=1 _password=1
  [ -n "$admin_username" ] && _username=0
  [ -n "$admin_password" ] && _password=0
  if [ "$(( _username ^ _password ))" -eq 1 ]; then
    die "--admin-username and --admin-password must be specified together"
  fi

  echo "Initializing RightSizer for user $target_user"
  if user_exists "$target_user"; then
    echo "User already exists"
  else
    echo "User does not exist. Creating..."
    sudo useradd --create-home --shell /bin/bash --user-group "$target_user" || die "could not create a user"
  fi

  if [ -n "$public_ssh_key" ]; then
    echo "Public SSH key was given. Adding this key to user's authorized_keys"
    sudo su - "$target_user" <<EOF
    mkdir -p .ssh
    chmod 700 .ssh
    echo "$public_ssh_key" >> .ssh/authorized_keys
    chmod 600 .ssh/authorized_keys
EOF
  fi
  local latest_release python_bin
  latest_release="$(get_latest_local_release)"
  validate_cli_artifacts "$latest_release"
  python_bin="$(check_modular_cli_python_compatibility "$latest_release")"
  echo "Installing CLIs for $target_user"
  sudo su - "$target_user" <<EOF >/dev/null
  # "$python_bin" -m pip install --user --break-system-packages "$R8S_RELEASES_PATH/$latest_release/${OBFUSCATOR_ARTIFACT_NAME}[xlsx]"
  MODULAR_CLI_ENTRY_POINT=$MODULAR_CLI_ENTRY_POINT "$python_bin" -m pip install --user --break-system-packages "$R8S_RELEASES_PATH/$latest_release/$MODULAR_CLI_ARTIFACT_NAME"
EOF

  local err=0
  kubectl exec service/modular-api -- ./modular.py user describe --username "$target_user" &>/dev/null || err=1

  if [ "$err" -ne 0 ]; then
    echo "Creating new modular-api user"
    new_password="$(generate_password 20 -hex)"
    api_path="http://$(minikube_ip):32105"
    kubectl exec service/modular-api -- ./modular.py user add --username "$target_user" --group admin_group --password "$new_password"
    sudo su - "$target_user" <<EOF
    echo "Logging in to modular-cli"
    ~/.local/bin/syndicate setup --username "$target_user" --password "$new_password" --api_path "$api_path"
    ~/.local/bin/syndicate login
EOF
  else
    echo "Modular api user has been initialized before"
  fi


  if [ -n "$re_username" ]; then
    echo "Logging in to RightSizer"
    sudo su - "$target_user" <<EOF
    ~/.local/bin/syndicate r8s configure --api_link http://rightsizer:8000/r8s
    ~/.local/bin/syndicate r8s login --username "$r8s_username" --password "$r8s_password"
EOF
  fi

  if [ -n "$admin_username" ]; then
    echo "Logging in to Modular Service"
    sudo su - "$target_user" <<EOF
    ~/.local/bin/syndicate admin configure --api_link http://modular-service:8040/dev
    ~/.local/bin/syndicate admin login --username "$admin_username" --password "$admin_password"
EOF
  fi
  echo "Done"
}

pull_artifacts() {
  # downloads all necessary files from the given github release tag. Make sure the release exists
  mkdir -p "$R8S_RELEASES_PATH/$1"
  wget -q -O "$R8S_RELEASES_PATH/$1/$MODULAR_CLI_ARTIFACT_NAME" "https://github.com/$GITHUB_REPO/releases/download/$1/$MODULAR_CLI_ARTIFACT_NAME" || warn "could not download $MODULAR_CLI_ARTIFACT_NAME from release $1"
#  wget -q -O "$R8S_RELEASES_PATH/$1/$OBFUSCATOR_ARTIFACT_NAME" "https://github.com/$GITHUB_REPO/releases/download/$1/$OBFUSCATOR_ARTIFACT_NAME" || warn "could not download $OBFUSCATOR_ARTIFACT_NAME from release $1"
  wget -q -O "$R8S_RELEASES_PATH/$1/$R8S_INIT_ARTIFACT_NAME" "https://github.com/$GITHUB_REPO/releases/download/$1/$R8S_INIT_ARTIFACT_NAME" || warn "could not download $R8S_INIT_ARTIFACT_NAME from release $1"
}
update_r8s_init() {
  # assuming that the target version already exists locally
  sudo ln -sf "$R8S_RELEASES_PATH/$1/$R8S_INIT_ARTIFACT_NAME" /usr/local/bin/r8s-init || {
    warn "Could not link r8s-init to /usr/local/bin/r8s-init"
    return 1
  }
  if [ ! -x "$R8S_RELEASES_PATH/$1/$R8S_INIT_ARTIFACT_NAME" ]; then
    sudo chmod +x "$R8S_RELEASES_PATH/$1/$R8S_INIT_ARTIFACT_NAME" || {
      warn "Could not add x permission to r8s-init"
      return 1
    }
  fi
}
perform_self_update() {
  local tag asset new_version
  tag="$(jq -r '.tag_name' <<<"$1")"

  if ! asset="$(find_asset_by_name "$1" "$R8S_INIT_ARTIFACT_NAME")"; then
    return 1
  fi
  if check_asset_digest "$SELF_PATH" "$asset"; then
    return 0
  fi

  pull_artifact "$R8S_RELEASES_PATH/$tag" "$asset" || {
    warn "could not pull self update artifact $R8S_INIT_ARTIFACT_NAME"
    return 1
  }
  update_r8s_init "$tag" || {
    warn "could not update r8s-init to $tag"
    return 1
  }
  new_version=$("$SELF_PATH" --version)
  echo "Automatically updated r8s-init from $VERSION to $new_version"
  exec "$SELF_PATH" "${_ORIGINAL_ARGS[@]}"
}
warn_if_update_available() {
  local current_release release_data
  current_release="$(get_helm_release_version "$HELM_RELEASE_NAME")" || return 1
  if release_data="$(get_new_github_release "$current_release")"; then
    warn "new $(get_release_type "$release_data") $(jq -r '.tag_name' <<<"$release_data") is available. Use 'r8s-init update'"
  fi
}
make_update_notification() {
  if [ ! -f "$UPDATE_NOTIFICATION_FILE" ]; then
    warn_if_update_available || return 1
    echo "$UPDATE_NOTIFICATION_PERIOD:$(($(date +%s) / UPDATE_NOTIFICATION_PERIOD))" >"$UPDATE_NOTIFICATION_FILE"
    return
  fi
  local period passed
  IFS=':' read -r period passed <"$UPDATE_NOTIFICATION_FILE"
  if [ "$(($(date +%s) / period))" -ne "$passed" ]; then
    warn_if_update_available || return 1
    echo "$UPDATE_NOTIFICATION_PERIOD:$(($(date +%s) / UPDATE_NOTIFICATION_PERIOD))" >"$UPDATE_NOTIFICATION_FILE"
  fi
}
verify_installation() {
  if [ -f "$R8S_LOCAL_PATH/.success" ]; then
    return 0
  fi
  local passed=""
  if [ -f "$LOG_PATH" ]; then
    passed="$(($(date +%s) - $(stat --format "%W" "$LOG_PATH")))"
  fi
  if [ -z "$passed" ] || [ "$passed" -gt "$INSTALLATION_PERIOD_THRESHOLD" ]; then
    echo "RightSizer does not appear to be initialized. Check $LOG_PATH for details." >&2
    exit 1
  fi
  echo "RightSizer is being initialized for the first time. Please wait. Approximately $(date -d@"$(("$INSTALLATION_PERIOD_THRESHOLD" - "$passed"))" -u "+%M minute(s) %S second(s)") left" >&2
  exit 1
}

cmd_update() {
  local opts auto_yes=0 r_name=$HELM_RELEASE_NAME r_version release_data latest_tag backup_name="" iter_params=() check=0 same_version=0 do_backup=1 update_defectdojo=0
  opts="$(getopt -o "hy" --long "help,yes,check,no-backup,defectdojo,allow-prereleases,same-version,backup-name:,helm-release-name:" -n "$PROGRAM" -- "$@")"
  eval set -- "$opts"
  while true; do
    case "$1" in
      '-h'|'--help') cmd_update_usage; exit 0 ;;
      '-y'|'--yes') auto_yes=1; shift ;;
      '--check') check=1; shift ;;
      '--no-backup') do_backup=0; shift ;;
      '--allow-prereleases') iter_params=(--prerelease --draft); shift ;;
      '--same-version') same_version=1; shift ;;
      '--defectdojo') update_defectdojo=1; shift ;;
      '--helm-release-name') r_name="$2"; shift 2 ;;
      '--backup-name') backup_name="$2"; shift 2 ;;
      '--') shift; break ;;
    esac
  done

  if [ "$update_defectdojo" -eq 1 ]; then
    [ "$check" -eq 1 ] && die "--check is currently not supported for Defect Dojo"
    echo "Going to update Defect Dojo chart"
    if [ "$do_backup" -eq 1 ]; then
      [ -z "$backup_name" ] && backup_name="$AUTO_BACKUP_PREFIX$(date +%s)"
      echo "Making backup $backup_name"
      cmd_backup_create --name "$backup_name" --volumes=defectdojo-cache,defectdojo-data,defectdojo-media
    fi
    helm repo update syndicate
    if ! helm upgrade "$DEFECTDOJO_HELM_RELEASE_NAME" syndicate/defectdojo --wait; then
      warn "helm upgrade failed. Rolling back to the previous version..."
      helm rollback "$DEFECTDOJO_HELM_RELEASE_NAME" 0 --wait || die "Helm rollback failed"
      exit 1
    else
      echo "helm upgrade was successful"
    fi
    exit 0
  fi

  r_version="$(get_helm_release_version "$r_name")"
  if [ "$same_version" -eq 1 ]; then
    release_data="$(get_github_release_by_tag "$r_version")" || warn "could not get release by tag $r_version"
    latest_tag="$r_version"
  else
    if ! release_data="$(get_new_github_release "$r_version" "${iter_params[@]}")"; then
      echo "Up-to-date"
      exit 0
    fi
    latest_tag="$(jq -r '.tag_name' <<<"$release_data")"
  fi

  if [ "$check" -eq 1 ]; then
    warn "new $(get_release_type "$release_data") $latest_tag is available. Use 'r8s-init update'"
    exit 1
  fi
  # TODO Delete && [ "$same_version" -eq 0 ] from condition
  if [ -n "$release_data" ] && [ -z "$FORBID_SELF_UPDATE" ] && [ "$same_version" -eq 0 ]; then
    perform_self_update "$release_data" || true
  fi

  echo "The current installed version is $r_version"
  echo "New github $(get_release_type "$release_data") $latest_tag is available"
  echo "Going to update to $latest_tag"
  [[ $auto_yes -eq 1 ]] || yesno "Do you want to update?"
  echo "Updating to $latest_tag"
  if [ "$do_backup" -eq 1 ]; then
    [ -z "$backup_name" ] && backup_name="$AUTO_BACKUP_PREFIX$(date +%s)"
    echo "Making backup $backup_name"
    cmd_backup_create --name "$backup_name" --volumes=minio,mongo,vault
  fi
  echo "Pulling new artifacts"
  pull_artifacts "$latest_tag"
  echo "Updating helm repo"
  helm repo update syndicate
  helm search repo syndicate/rightsizer --version "$latest_tag" --fail-on-no-result >/dev/null 2>&1 || die "$latest_tag version of $r_name chart not found. Cannot update"
  echo "Upgrading $r_name chart to $latest_tag version"
  if ! helm upgrade "$HELM_RELEASE_NAME" syndicate/rightsizer --version "$latest_tag" --wait; then
    warn "helm upgrade failed. Rolling back to the previous version..."
    helm rollback "$HELM_RELEASE_NAME" 0 --wait || die "Helm rollback failed"
    exit 1
  else
    echo "helm upgrade was successful"
  fi
#  echo "Upgrading obfuscation manager"
#  pip3 install --user --break-system-packages --upgrade "$R8S_RELEASES_PATH/$latest_tag/${OBFUSCATOR_ARTIFACT_NAME}[xlsx]" >/dev/null
  if [ -f "$R8S_RELEASES_PATH/$latest_tag/$MODULAR_CLI_ARTIFACT_NAME" ]; then
    echo "Upgrading modular CLI"
    local python_bin
    python_bin="$(check_modular_cli_python_compatibility "$latest_tag")"
    pip_install_artifact "$python_bin" "$R8S_RELEASES_PATH/$latest_tag/$MODULAR_CLI_ARTIFACT_NAME" --upgrade >/dev/null
  fi
  if [ -f "$R8S_RELEASES_PATH/$latest_tag/$R8S_INIT_ARTIFACT_NAME" ]; then
    echo "Updating r8s-init"
    update_r8s_init "$latest_tag" || true
  fi
  echo "Done"
}

cmd_update_list() {
  local opts iter_params=()
  opts="$(getopt -o "h" --long "help,allow-prereleases" -n "$PROGRAM" -- "$@")"
  eval set -- "$opts"
  while true; do
    case "$1" in
      -h|--help) cmd_update_list_usage; exit 0 ;;
      --allow-prereleases) iter_params=(--prerelease --draft); shift ;;
      '--') shift; break ;;
    esac
  done

  local tag_name current_release
  current_release="$(get_helm_release_version "$HELM_RELEASE_NAME")"
  while IFS= read -r item; do
    tag_name=$(jq -r '.tag_name' <<<"$item")
    if [[ "$current_release" == "$tag_name" ]]; then
      jq -rj '"\(.tag_name)* \(.published_at) \(.html_url) \(.prerelease) \(.draft)"' <<<"$item" | colorize GREEN
    fi
    if dpkg --compare-versions "$tag_name" le "$current_release" 2>/dev/null; then
      break
    fi
    jq -rj '"\(.tag_name) \(.published_at) \(.html_url) \(.prerelease) \(.draft)\n"' <<<"$item"
  done < <(iter_github_releases "${iter_params[@]}") | column --table --table-columns RELEASE,DATE,URL,PRERELEASE,DRAFT
}

cmd_health() {
  local opts
  opts="$(getopt -o "h" --long "help" -n "$PROGRAM" -- "$@")"
  eval set -- "$opts"
  while true; do
    case "$1" in
      -h|--help) cmd_health_usage; exit 0 ;;
      '--') shift; break ;;
    esac
  done
  declare -A checks
  checks["1:RightSizer initialized"]="test -f $R8S_LOCAL_PATH/.success"
  checks["2:RightSizer helm release"]="helm get metadata $HELM_RELEASE_NAME"
  checks["3:Syndicate entrypoint"]="syndicate version"
  checks["4:RightSizer health check"]="syndicate r8s health_check"
  checks["5:Defect Dojo helm release"]="helm get metadata $DEFECTDOJO_HELM_RELEASE_NAME"

  while IFS= read -r key; do
    IFS=":" read -r order name <<<"$key"
    if ${checks[$key]} >/dev/null 2>&1; then
      printf "%s|%s|ok\n" "$order" "$name" | colorize GREEN
    else
      printf "%s|%s|failed\n" "$order" "$name" | colorize RED
      exit 1
    fi
  done < <(printf "%s\n" "${!checks[@]}" | sort) | column --table -s "|" --table-columns "№,CHECK,STATUS"
}

cmd_doctor() {
  local opts release="" latest_local_release="" release_path=""
  local python_bin="" required_version="" current_version=""
  local status=0

  opts="$(getopt -o "h" --long "help,release:" -n "$PROGRAM doctor" -- "$@")" \
    || die "$(cmd_unrecognized)"
  eval set -- "$opts"
  while true; do
    case "$1" in
      -h|--help) cmd_doctor_usage; exit 0 ;;
      --release) release="$2"; shift 2 ;;
      '--') shift; break ;;
    esac
  done

  if [ -n "$release" ]; then
    latest_local_release="$release"
  else
    latest_local_release="$(get_latest_local_release 2>/dev/null || true)"
  fi

  echo "r8s-init environment check"
  echo

  if [ -n "$latest_local_release" ]; then
    release_path="$R8S_RELEASES_PATH/$latest_local_release"
    echo "[OK] Local release resolved: $latest_local_release"

    if release_metadata_exists "$latest_local_release"; then
      echo "[OK] Release metadata found: $(release_metadata_path "$latest_local_release")"
    else
      echo "[WARN] Release metadata not found. Treating release as legacy."
    fi

    if [ -d "$release_path" ]; then
      echo "[OK] Release directory found: $release_path"
    else
      echo "[ERROR] Release directory was not found: $release_path"
      status=1
    fi

    if [ -f "$release_path/$MODULAR_CLI_ARTIFACT_NAME" ]; then
      echo "[OK] Modular CLI artifact found"
    else
      echo "[ERROR] Modular CLI artifact not found: $release_path/$MODULAR_CLI_ARTIFACT_NAME"
      status=1
    fi

    required_version="$(get_modular_cli_min_python "$latest_local_release")"
    echo "[INFO] Modular CLI Python requirement: >=$required_version"
  else
    echo "[WARN] Could not resolve latest local release from $R8S_RELEASES_PATH"
    required_version="$R8S_DEFAULT_MODULAR_CLI_MIN_PYTHON"
    status=1
  fi

  python_bin="$(resolve_python_bin 2>/dev/null || true)"

  if [ -n "$python_bin" ]; then
    current_version="$(python_version "$python_bin")"
    echo "[INFO] Resolved Python interpreter: $python_bin"
    echo "[INFO] Resolved Python version: $current_version"

    if python_satisfies "$python_bin" "$required_version"; then
      echo "[OK] Python requirement satisfied"
    else
      echo "[WARN] Python requirement is not satisfied"
      echo
      echo "Recommended command:"
      echo "  R8S_PYTHON_BIN=/usr/local/bin/python${required_version} $PROGRAM init --user <username>"
      status=1
    fi
  else
    echo "[ERROR] Could not resolve Python interpreter"
    status=1
  fi

  return "$status"
}

cmd_nginx() {
  case "$1" in
    -h|--help) shift; cmd_nginx_usage "$@" ;;
    enable) shift; cmd_nginx_enable "$@" ;;
    disable) shift; cmd_nginx_disable "$@" ;;
    ls) shift; cmd_nginx_list "$@" ;;
    '') cmd_nginx_list "$@" ;;
    *) die "$(cmd_unrecognized)" ;;
  esac
}

cmd_nginx_list() {
  # TODO can be rewritten
  local port filename rows="" enabled=":"
  for file in /etc/nginx/sites-enabled/*; do
    port="$(grep -oP "listen \K\d+" < "$file")"
    filename="${file##*/}"
    rows+="$filename Enabled $port\n"
    enabled+="$filename:"
  done
  for file in /etc/nginx/sites-available/*; do
    filename="${file##*/}"
    if [[ "$enabled" = *:$filename:* ]]; then
      continue
    fi
    port="$(grep -oP "listen \K\d+" < "$file")"
    rows+="$filename Disabled $port\n"
  done
  printf "%b" "$rows" | column --table --table-columns NAME,STATUS,PORT
}

cmd_nginx_enable() {
  printf "Not implemented yet. Create link from /etc/nginx/sites-available to /etc/nginx/sites-enabled manually. Expose existing k8s service manually\n"
  exit 1
}

cmd_nginx_disable() {
  printf "Not implemented yet\n"
  exit 1
}

make_backup() {
  # accepts k8s persistent volume name as first parameter and destination folder as second parameter.
  local host_path
  host_path="$(kubectl get pv "$1" -o jsonpath="{.spec.hostPath.path}")"
  if [ -z "$host_path" ]; then
    warn "volume $1 does not have hostPath" >&2
    return 1
  fi
  minikube ssh "sudo tar -czf /tmp/$1.tar.gz -C $host_path ."
  minikube cp "$HELM_RELEASE_NAME:/tmp/$1.tar.gz" "$2/"
  sha256sum "$2/$1.tar.gz" > "$2/$1.sha256"
}
restore_backup() {
  # accepts k8s persistent volume name as first parameter and folder with backup as second parameter
  local host_path
  host_path="$(kubectl get pv "$1" -o jsonpath="{.spec.hostPath.path}")"
  if [ -z "$host_path" ]; then
    warn "volume $1 does not have hostPath"
    return 1
  fi
  if [ ! -f "$2/$1.tar.gz" ]; then
    warn "tar archive does not exist for $1"
    return 1
  fi
  if [ ! -f "$2/$1.sha256" ]; then
    warn "sha256 sum does not match for volume $1"
    return 1
  fi
  sha256sum "$2/$1.sha256" --check || return 1
  minikube cp "$2/$1.tar.gz" "$HELM_RELEASE_NAME:/tmp/$1.tar.gz"
  minikube ssh "sudo rm -rf $host_path; sudo mkdir -p $host_path ; sudo tar --same-owner --overwrite -xzf /tmp/$1.tar.gz -C $host_path"
}
cmd_backup() {
  case "$1" in
    -h|--help) shift; cmd_backup_usage "$@" ;;
    create) shift; cmd_backup_create "$@" ;;
    ls) shift; cmd_backup_list "$@" ;;
    rm) shift; cmd_backup_rm "$@";;
    restore) shift; cmd_backup_restore "$@" ;;
    '') cmd_backup_list "$@" ;;
    *) die "$(cmd_unrecognized)" ;;
  esac
}

resolve_backup_path() {
  if [ -n "$1" ]; then
    [ -n "$2" ] && warn "--version is ignored because --path is specified" >&2
    echo "$1" # ignoring version if path is specified
  elif [ -n "$2" ]; then
    echo "$R8S_BACKUPS_PATH/$2"
  else
    echo "$R8S_BACKUPS_PATH/$(get_helm_release_version "$HELM_RELEASE_NAME")"
  fi
}

cmd_backup_list() {
  local opts version="" path="" pvs size
  opts="$(getopt -o "hv:p:" --long "help,version:,path:" -n "$PROGRAM" -- "$@")"
  eval set -- "$opts"
  while true; do
    case "$1" in
      -h|--help) cmd_backup_list_usage; exit 0 ;;
      -v|--version) version="$2"; shift 2 ;;
      -p|--path) path="$2"; shift 2 ;;
      '--') shift; break ;;
    esac
  done
  path="$(resolve_backup_path "$path" "$version")"
  if [ ! -d "$path" ] || [ -z "$(ls -A "$path")" ]; then
    echo "No backups found in $path" >&2
    exit 0
  fi
  find "$path/"* -maxdepth 1 -type d -print0 | xargs -0 stat --format "%W %n" | sort -r | while IFS=' ' read -r ts fp; do
    pvs=$(find "$fp" -name '*.tar.gz' -type f -exec basename --suffix='.tar.gz' '{}' \; | sort | tr '\n' ',' | sed 's/,$//')
    size="$(du -hsc "$fp"/*.tar.gz 2>/dev/null | grep total | cut -f1 || true)"
    printf "%s|%s|%s|%s\n" "$(basename "$fp")" "$(date --date="@$ts")" "${size:-0}" "$pvs"
  done | column --table -s "|" --table-columns NAME,DATE,SIZE,PVs
}

cmd_backup_rm() {
  local opts version="" path="" name="" auto_yes=0
  opts="$(getopt -o "n:hyv:p:" --long "name:,help,yes,version:,path:" -n "$PROGRAM" -- "$@")"
  eval set -- "$opts"
  while true; do
    case "$1" in
      -h|--help) cmd_backup_rm_usage; exit 0 ;;
      -v|--version) version="$2"; shift 2 ;;
      -p|--path) path="$2"; shift 2 ;;
      -n|--name) name="$2"; shift 2 ;;
      -y|--yes) auto_yes=1; shift ;;
      '--') shift; break ;;
    esac
  done
  [ -z "$name" ] && die "--name is required"
  path="$(resolve_backup_path "$path" "$version")"
  if [ ! -d "$path/$name" ]; then
    echo "All traces of '$name' (from $path) are removed"
    exit 0
  fi
  [[ $auto_yes -eq 1 ]] || yesno "Do you really want to remove backup?"
  rm -rf "${path:?}/$name"
  echo "All traces of '$name' (from $path) are removed"
}

cmd_backup_create() {
  local opts path="" name="" volumes="" vol
  opts="$(getopt -o "n:hp:" --long "name:,help,path:,volumes:" -n "$PROGRAM" -- "$@")"
  eval set -- "$opts"
  while true; do
    case "$1" in
      -h|--help) cmd_backup_create_usage; exit 0 ;;
      -p|--path) path="$2"; shift 2 ;;
      -n|--name) name="$2"; shift 2 ;;
      --volumes) volumes="$2"; shift 2 ;;
      '--') shift; break ;;
    esac
  done
  [ -z "$name" ] && die "--name is required"
  [ -z "$path" ] && path="$R8S_BACKUPS_PATH/$(get_helm_release_version "$HELM_RELEASE_NAME")"
  [ -d "$path/$name" ] && die "'$name' already exists"
  mkdir -p "$path/$name"
  if [ -z "$volumes" ]; then
    for vol in $(kubectl get pv -o=jsonpath="{.items[*].metadata.name}"); do
      echo "Making backup for volume $vol"
      make_backup "$vol" "$path/$name" || warn "could not make backup"
    done
  else
    local items
    IFS=',' read -ra items <<< "$volumes"
    for vol in "${items[@]}"; do
      if ! kubectl get pv "$vol" >/dev/null 2>&1; then
        warn "'$vol' volume does not exist" >&2
        continue
      fi
      echo "Making backup for volume '$vol'"
      make_backup "$vol" "$path/$name" || warn "could not make backup"
    done
  fi
}
cmd_backup_restore() {
  local opts path="" name="" volumes="" version="" force=0 current_release vol
  opts="$(getopt -o "n:hp:v:f" --long "name:,help,path:,version:,volumes:,force" -n "$PROGRAM" -- "$@")"
  eval set -- "$opts"
  while true; do
    case "$1" in
      -h|--help) cmd_backup_restore_usage; exit 0 ;;
      -p|--path) path="$2"; shift 2 ;;
      -v|--version) version="$2"; shift 2 ;;
      -n|--name) name="$2"; shift 2 ;;
      -f|--force) force=1; shift ;;
      --volumes) volumes="$2"; shift 2 ;;
      '--') shift; break ;;
    esac
  done
  [ -z "$name" ] && die "--name is required"
  current_release="$(get_helm_release_version "$HELM_RELEASE_NAME")"
  [ "$force" -eq 0 ] && [ -n "$version" ] && [ "$version" != "$current_release" ] && die "current release $current_release does not match to the backup version $version. Specify --force if you really want to restore backup"
  path="$(resolve_backup_path "$path" "$version")"
  [ ! -d "$path/$name" ] && die "backup '$name' (from $path) not found"

  declare -a items
  if [ -z "$volumes" ]; then
    while IFS= read -r -d ''; do
      items+=("$(basename --suffix='.tar.gz' "$REPLY")")
    done < <(find "$path/$name" -name '*.tar.gz' -type f -print0)
  else
    IFS=',' read -ra items <<< "$volumes"
  fi
  echo "${items[@]}"

  for vol in "${items[@]}"; do
    if ! kubectl get pv "$vol" >/dev/null 2>&1; then
      warn "'$vol' volume does not exist" >&2
      continue
    fi
    echo "Restoring volume '$vol'"
    restore_backup "$vol" "$path/$name" || die "could not restore backup"
  done
}

# Start
VERSION="1.2.0"
PROGRAM="${0##*/}"
COMMAND="$1"
SELF_PATH=/usr/local/bin/r8s-init
readonly _ORIGINAL_ARGS=("$@")

# Some variables that configure how cli behaves
R8S_PYTHON_BIN="${R8S_PYTHON_BIN:-}"
R8S_RELEASE_METADATA_NAME="${R8S_RELEASE_METADATA_NAME:-release.json}"
# Defaults for new releases when release.json exists but some fields are missing
R8S_DEFAULT_MODULAR_CLI_MIN_PYTHON="${R8S_DEFAULT_MODULAR_CLI_MIN_PYTHON:-3.14}"
R8S_PYTHON_COMPAT_MODE="${R8S_PYTHON_COMPAT_MODE:-error}"
# Defaults for old releases without release.json
R8S_LEGACY_MODULAR_CLI_MIN_PYTHON="${R8S_LEGACY_MODULAR_CLI_MIN_PYTHON:-3.10}"
R8S_LEGACY_PYTHON_COMPAT_MODE="${R8S_LEGACY_PYTHON_COMPAT_MODE:-warn}"
R8S_LOCAL_PATH="${R8S_LOCAL_PATH:-/usr/local/r8s}"
R8S_RELEASES_PATH="${R8S_RELEASES_PATH:-$R8S_LOCAL_PATH/releases}"
R8S_BACKUPS_PATH="${R8S_BACKUPS_PATH:-$R8S_LOCAL_PATH/backups}"
GITHUB_REPO="${GITHUB_REPO:-epam/r8s}"
HELM_RELEASE_NAME="${HELM_RELEASE_NAME:-rightsizer}"
DEFECTDOJO_HELM_RELEASE_NAME="${DEFECTDOJO_HELM_RELEASE_NAME:-defectdojo}"
MODULAR_SERVICE_USERNAME="${MODULAR_SERVICE_USERNAME:-customer_admin}"
RIGHTSIZER_USERNAME="${RIGHTSIZER_USERNAME:-customer_admin}"
CURRENT_ACCOUNT_TENANT_NAME="${CURRENT_ACCOUNT_TENANT_NAME:-CURRENT_ACCOUNT}"
AUTO_BACKUP_PREFIX="${AUTO_BACKUP_PREFIX:-autobackup-}"
FORBID_SELF_UPDATE="${FORBID_SELF_UPDATE:-}"
# regions that will be allowed to activate
AWS_REGIONS="${AWS_REGIONS:-us-east-1 us-east-2 us-west-1 us-west-2 af-south-1 ap-east-1 ap-south-2 ap-southeast-3 ap-southeast-4 ap-south-1 ap-northeast-3 ap-northeast-2 ap-southeast-1 ap-southeast-2 ap-northeast-1 ca-central-1 ca-west-1 eu-central-1 eu-west-1 eu-west-2 eu-south-1 eu-west-3 eu-south-2 eu-north-1 eu-central-2 il-central-1 me-south-1 me-central-1 sa-east-1 us-gov-east-1 us-gov-west-1}"

RIGHTSIZER_SECRET_NAME=rightsizer-secret
MODULAR_API_SECRET_NAME=modular-api-secret
MODULAR_SERVICE_SECRET_NAME=modular-service-secret
DEFECTDOJO_SECRET_NAME=defectdojo-secret

MODULAR_CLI_ARTIFACT_NAME=modular_cli.tar.gz
#OBFUSCATOR_ARTIFACT_NAME=r8s_obfuscator.tar.gz
R8S_INIT_ARTIFACT_NAME=r8s-init.sh
MODULAR_CLI_ENTRY_POINT=syndicate

GITHUB_CURL_HEADERS=('-H' 'X-GitHub-Api-Version: 2022-11-28')
if [ -n "$GITHUB_TOKEN" ]; then
  GITHUB_CURL_HEADERS+=('-H' "Authorization: Bearer $GITHUB_TOKEN")
fi
readonly GITHUB_CURL_HEADERS

MODULAR_ADMIN_POLICY='[{"Description": "Admin policy", "Module": "*", "Effect": "Allow", "Resources": ["*"]}, {"Effect": "Deny", "Description": "Prohibited commands", "Module": "r8s", "Resources": ["algorithm:add", "algorithm:update_clustering_settings", "algorithm:update_general_settings", "algorithm:update_metric_format", "algorithm:update_recommendation_settings", "report:initiate_tenant_mail_report"]}]'
FIRST_USER="${FIRST_USER:-$(getent passwd 1000 | cut -d : -f 1)}"

DO_NOT_ACTIVATE_LICENSE="${DO_NOT_ACTIVATE_LICENSE:-}"
DO_NOT_ACTIVATE_TENANT="${DO_NOT_ACTIVATE_TENANT:-}"
DO_NOT_ACTIVATE_STORAGE="${DO_NOT_ACTIVATE_STORAGE:-}"

# NOTE: Keep in sync with ami-initialize.sh
readonly SUPPORT_EMAIL="SupportSyndicateTeam@epam.com"

# in seconds
readonly INSTALLATION_PERIOD_THRESHOLD="${INSTALLATION_PERIOD_THRESHOLD:-900}"
readonly LOG_PATH="${LOG_PATH:-/var/log/r8s-init.log}"

# in seconds
readonly UPDATE_NOTIFICATION_PERIOD="${UPDATE_NOTIFICATION_PERIOD:-3600}"
readonly UPDATE_NOTIFICATION_FILE="$R8S_LOCAL_PATH/.update-notification"

if [ ! "$1" = "init" ] && [ ! "$1" = '--system' ] && [ ! "$1" = '--user' ]; then
  verify_installation
fi

make_update_notification || true

case "$1" in
  backup) shift; cmd_backup "$@" ;;
  check|doctor) shift; cmd_doctor "$@" ;;
  health) shift; cmd_health "$@" ;;
  help|-h|--help) shift; cmd_usage "$@" ;;
  version|--version) shift; cmd_version "$@" ;;
  update) shift; cmd_update "$@" ;;
  list) shift; cmd_update_list "$@" ;;
  init) shift; cmd_init "$@" ;;
  nginx) shift; cmd_nginx "$@" ;;
  --system|--user) cmd_init "$@" ;;  # redirect to init as default one
  '') cmd_usage ;;
  *) die "$(cmd_unrecognized)" ;;
esac
exit 0