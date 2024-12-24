#!/bin/bash

set -eo pipefail

cmd_usage() {
  cat <<EOF
Manage RightSizer installation

Usage:
  $PROGRAM [command]

Available Commands:
  backup   Allow to manage backups
  help     Show help message
  init     Initialize RightSizer installation
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
  $PROGRAM $COMMAND -y

Options:
  -h, --help           Show this message and exit
  -y, --yes            Automatic yes to prompts
  --helm-release-name  RightSizer helm release name (default "$HELM_RELEASE_NAME")
  --backup-name        Backup name to make before the update (default "$AUTO_BACKUP_PREFIX\$timestamp")
EOF
}
# todo add force and release version

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


cmd_version() { echo "$VERSION"; }
die() { echo "Error:" "$@" >&2; exit 1; }
warn() { echo "Warning:" "$@" >&2; }
cmd_unrecognized() {
  cat <<EOF
Error: unrecognized command \`$PROGRAM $COMMAND\`
Try '$PROGRAM --help' for more information
EOF
}


# helper functions
get_latest_local_release() { ls "$R8S_RELEASES_PATH" | sort -r | head -n 1; }
get_helm_release_version() {
  # currently the version of rightsizer chart corresponds to the version of app inside
  helm get metadata "$1" -o json | jq -r '.version'
}
get_latest_release_tag() {
  curl -fLs "https://api.github.com/repos/$GITHUB_REPO/releases/latest" | jq -r '.tag_name' || die "no latest release for $GITHUB_REPO found"
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
#  echo "Installing obfuscation manager"
#  pip3 install --user --break-system-packages --upgrade "$R8S_RELEASES_PATH/$(get_latest_local_release)/${OBFUSCATOR_ARTIFACT_NAME}[xlsx]"
  echo "Installing modular-cli"
  MODULAR_CLI_ENTRY_POINT=$MODULAR_CLI_ENTRY_POINT pip3 install --user --break-system-packages --upgrade "$R8S_RELEASES_PATH/$(get_latest_local_release)/$MODULAR_CLI_ARTIFACT_NAME"

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

  lm_response=$(get_kubectl_secret lm-data lm-response)
  customer_name=$(echo "$lm_response" | jq ".customer_name" -r)

  echo "Generating passwords for modular-service and rightsizer non-system users"
  modular_service_password="$(generate_password)"
  rightsizer_password="$(generate_password)"
  patch_kubectl_secret "$RIGHTSIZER_SECRET_NAME" "admin-password" "$rightsizer_password"
  patch_kubectl_secret "$MODULAR_SERVICE_SECRET_NAME" "admin-password" "$modular_service_password"

  echo "Creating modular service customer and its user"
  syndicate admin signup --username "$MODULAR_SERVICE_USERNAME" --password "$modular_service_password" --customer_name "$customer_name" --customer_display_name "$customer_name" --customer_admin admin@example.com --json

  echo "Creating rightsizer lm setting"
  LM_API_LINK=$(get_kubectl_secret lm-data api-link)
  syndicate r8s setting config add --host $LM_API_LINK --port 443 --protocol "HTTPS" --stage '/' --json

  echo "Creating rightsizer lm client"
  syndicate r8s setting client add --key_id "$(echo "$lm_response" | jq ".private_key.key_id" -r)" --algorithm "$(echo "$lm_response" | jq ".private_key.algorithm" -r)" --private_key "$(echo "$lm_response" | jq ".private_key.value" -r)" --format "PEM" --b64encoded --json

  echo "Creating rightsizer customer users"
  syndicate r8s register --username "$RIGHTSIZER_USERNAME" --password "$rightsizer_password" --role_name admin_role --customer_id "$customer_name" --json

  echo "Logging in as customer users"
  syndicate admin login --username "$MODULAR_SERVICE_USERNAME" --password "$modular_service_password" --json
  syndicate r8s login --username "$RIGHTSIZER_USERNAME" --password "$rightsizer_password" --json

  echo "Activating tenant for the current aws account"
  syndicate admin tenant create --name "$CURRENT_ACCOUNT_TENANT_NAME" --display_name "Tenant $(account_id)" --cloud AWS --account_id "$(account_id)" --primary_contacts admin@example.com --secondary_contacts admin@example.com --tenant_manager_contacts admin@example.com --default_owner admin@example.com --json

  echo "Activating region for tenant"
  for r in $AWS_REGIONS;
  do
    echo "Activating $r for tenant"
    syndicate admin tenant regions activate --tenant_name "$CURRENT_ACCOUNT_TENANT_NAME" --region_name "$r" --json > /dev/null
  done

  echo "Setting up RightSizer Licensed Application"
  output=$(syndicate r8s application licenses add --customer_id "$customer_name" --description "$customer_name application" --cloud "AWS" --tenant_license_key "$(echo "$lm_response" | jq ".tenant_license_key" -r)" --json)
  licensed_application_id=$(echo "$output" | jq ".items[0].application_id" -r)

  echo "Setting up Licensed Parent"
  syndicate r8s parent add --application_id "$licensed_application_id" --description "$customer_name parent" --scope "SPECIFIC" --tenant "$CURRENT_ACCOUNT_TENANT_NAME" --json

  echo "Setting up Metrics storage"
  syndicate r8s storage add --storage_name input_storage --type DATA_SOURCE --bucket_name r8s-metrics --json

  echo "Setting up Scan results storage"
  syndicate r8s storage add --storage_name output_storage --type STORAGE --bucket_name r8s-results --json

  echo "Setting up RIGHTSIZER Application"
  syndicate r8s application add --customer_id "$customer_name" --description "$customer_name application" --input_storage input_storage --output_storage output_storage --username "ADMIN" --password "ADMIN" --host "0.0.0.0" --port 8000 --protocol HTTP --json

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
  echo "Installing CLIs for $target_user"
  sudo su - "$target_user" <<EOF >/dev/null
  # pip3 install --user --break-system-packages "$R8S_RELEASES_PATH/$(get_latest_local_release)/${OBFUSCATOR_ARTIFACT_NAME}[xlsx]"
  MODULAR_CLI_ENTRY_POINT=$MODULAR_CLI_ENTRY_POINT pip3 install --user --break-system-packages "$R8S_RELEASES_PATH/$(get_latest_local_release)/$MODULAR_CLI_ARTIFACT_NAME"
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
  local err=0
  sudo cp "$R8S_RELEASES_PATH/$1/$R8S_INIT_ARTIFACT_NAME" /usr/local/bin/r8s-init || err=1
  if [ "$err" -eq 0 ]; then
    sudo chmod +x /usr/local/bin/r8s-init
  else
    echo "Could not update r8s-init"
  fi
}

cmd_update() {
  local opts auto_yes=0 r_name=$HELM_RELEASE_NAME r_version latest_tag backup_name=""
  opts="$(getopt -o "hy" --long "help,yes,helm-release-name:,backup-name:" -n "$PROGRAM" -- "$@")"
  eval set -- "$opts"
  while true; do
    case "$1" in
      '-h'|'--help') cmd_update_usage; exit 0 ;;
      '-y'|'--yes') auto_yes=1; shift ;;
      '--helm-release-name') r_name="$2"; shift 2 ;;
      '--backup-name') backup_name="$2"; shift 2 ;;
      '--') shift; break ;;
    esac
  done
  r_version="$(get_helm_release_version "$r_name")"
  echo "The current helm chart release is $r_version"
  latest_tag="$(get_latest_release_tag)"
  echo "Latest release available is $latest_tag"
  if [[ ! "$r_version" < "$latest_tag" ]]; then
    echo "Rightsizer chart is up-to-date"
    exit 0
  fi
  echo "New release $latest_tag is available."
  [[ $auto_yes -eq 1 ]] || yesno "Do you want to update?"
  echo "Updating to $latest_tag"
  [ -z "$backup_name" ] && backup_name="$AUTO_BACKUP_PREFIX$(date +%s)"
  echo "Making backup $backup_name"
  cmd_backup_create --name "$backup_name" --volumes=minio,mongo,vault
  echo "Pulling new artifacts"
  pull_artifacts "$latest_tag"
  echo "Updating helm repo"
  helm repo update syndicate
  helm search repo syndicate/rightsizer --version "$latest_tag" --fail-on-no-result >/dev/null 2>&1 || die "$latest_tag version of $r_name chart not found. Cannot update"
  echo "Upgrading $r_name chart to $latest_tag version"
  helm upgrade "$HELM_RELEASE_NAME" syndicate/rightsizer --version "$latest_tag"
#  echo "Upgrading obfuscation manager"
#  pip3 install --user --break-system-packages --upgrade "$R8S_RELEASES_PATH/$latest_tag/${OBFUSCATOR_ARTIFACT_NAME}[xlsx]" >/dev/null
  echo "Upgrading modular CLI"
  MODULAR_CLI_ENTRY_POINT=$MODULAR_CLI_ENTRY_POINT pip3 install --user --break-system-packages --upgrade "$R8S_RELEASES_PATH/$latest_tag/${MODULAR_CLI_ARTIFACT_NAME}" >/dev/null
  echo "Trying to update r8s-init"
  update_r8s_init "$latest_tag"
  echo "Done"
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
VERSION="1.0.0"
PROGRAM="${0##*/}"
COMMAND="$1"

# Some global constants
R8S_LOCAL_PATH=/usr/local/r8s
R8S_RELEASES_PATH=$R8S_LOCAL_PATH/releases
R8S_BACKUPS_PATH=$R8S_LOCAL_PATH/backups
GITHUB_REPO=epam/r8s
HELM_RELEASE_NAME=rightsizer
MODULAR_SERVICE_USERNAME="customer_admin"
RIGHTSIZER_USERNAME="customer_admin"
CURRENT_ACCOUNT_TENANT_NAME="CURRENT_ACCOUNT"
# regions that will be allowed to activate
AWS_REGIONS="us-east-1 us-east-2 us-west-1 us-west-2 af-south-1 ap-east-1 ap-south-2 ap-southeast-3 ap-southeast-4 ap-south-1 ap-northeast-3 ap-northeast-2 ap-southeast-1 ap-southeast-2 ap-northeast-1 ca-central-1 ca-west-1 eu-central-1 eu-west-1 eu-west-2 eu-south-1 eu-west-3 eu-south-2 eu-north-1 eu-central-2 il-central-1 me-south-1 me-central-1 sa-east-1 us-gov-east-1 us-gov-west-1"
AUTO_BACKUP_PREFIX="autobackup-"

RIGHTSIZER_SECRET_NAME=rightsizer-secret
MODULAR_API_SECRET_NAME=modular-api-secret
MODULAR_SERVICE_SECRET_NAME=modular-service-secret
DEFECTDOJO_SECRET_NAME=defectdojo-secret

MODULAR_CLI_ARTIFACT_NAME=modular_cli.tar.gz
#OBFUSCATOR_ARTIFACT_NAME=r8s_obfuscator.tar.gz
R8S_INIT_ARTIFACT_NAME=r8s-init.sh
MODULAR_CLI_ENTRY_POINT=syndicate
MODULAR_ADMIN_POLICY='[{"Description": "Admin policy", "Module": "*", "Effect": "Allow", "Resources": ["*"]}, {"Effect": "Deny", "Description": "Prohibited commands", "Module": "r8s", "Resources": ["algorithm:add", "algorithm:update_clustering_settings", "algorithm:update_general_settings", "algorithm:update_metric_format", "algorithm:update_recommendation_settings", "report:initiate_tenant_mail_report"]}]'
FIRST_USER=$(getent passwd 1000 | cut -d : -f 1)

case "$1" in
  backup) shift; cmd_backup "$@" ;;
  help|-h|--help) shift; cmd_usage "$@" ;;
  version|--version) shift; cmd_version "$@" ;;
  update) shift; cmd_update "$@" ;;
  init) shift; cmd_init "$@" ;;
  nginx) shift; cmd_nginx "$@" ;;
  --system|--user) cmd_init "$@" ;;  # redirect to init as default one
  '') cmd_usage ;;
  *) die "$(cmd_unrecognized)" ;;
esac
exit 0