#!/bin/bash

__usage="\
Usage: $0 [OPTIONS]

Options:
  -h, --help        Show this message and exit
  --system          Initialize R8S for the first time. Only possible for user with ($(id -un 1000)). Created necessary system entities
  --user            Initialize R8S for the given user
  --public-ssh-key  If specified will be added to user's authorized_keys.
  --r8s-username    R8s username to configure. Must be specified together with --r8s-password
  --r8s-password    R8s password to configure. Must be specified together with --r8s-username
  --admin-username  Modular Service username to configure. Must be specified together with --admin-password
  --admin-password  Modular Service password to configure. Must be specified together with --admin-username
"

usage() { echo "$__usage"; }
exit_badly() { echo "$1" >&2; exit 1; }


TEMP=$(getopt -o 'h' --long 'help,system,user:,public-ssh-key:,r8s-username:,r8s-password:,admin-username:,admin-password:' -n 'r8s-init.sh' -- "$@")
if [ $? -ne 0 ]; then
  exit_badly "$(usage)"
fi
eval set -- "$TEMP"
unset TEMP

while true; do
  case "$1" in
    '-h'|'--help') usage; exit 0 ;;
    '--system') init_system="true"; shift ;;
    '--user') target_user="$2"; shift 2 ;;
    '--public-ssh-key') public_ssh_key="$2"; shift 2 ;;
    '--r8s-username') r8s_username="$2"; shift 2 ;;
    '--r8s-password') r8s_password="$2"; shift 2 ;;
    '--admin-username') admin_username="$2"; shift 2 ;;
    '--admin-password') admin_password="$2"; shift 2 ;;
    '--') shift; break ;;
    *) exit_badly 'Internal Error' ;;
  esac
done
init_system="true"
# Constants
R8S_LOCAL_PATH=/usr/local/r8s
R8S_ARTIFACTS_PATH=$R8S_LOCAL_PATH/artifacts
R8S_SECRETS_PATH=$R8S_LOCAL_PATH/secrets

MODULAR_SERVICE_USERNAME="customer_admin"
R8S_USERNAME="customer_admin"
CURRENT_ACCOUNT_TENANT_NAME="CURRENT_ACCOUNT"
# regions that will be allowed to activate
AWS_REGIONS="us-east-1 us-east-2 us-west-1 us-west-2 af-south-1 ap-east-1 ap-south-2 ap-southeast-3 ap-southeast-4 ap-south-1 ap-northeast-3 ap-northeast-2 ap-southeast-1 ap-southeast-2 ap-northeast-1 ca-central-1 ca-west-1 eu-central-1 eu-west-1 eu-west-2 eu-south-1 eu-west-3 eu-south-2 eu-north-1 eu-central-2 il-central-1 me-south-1 me-central-1 sa-east-1 us-gov-east-1 us-gov-west-1"


R8S_PASSWORD_PATH=$R8S_SECRETS_PATH/r8s-pass
MODULAR_SERVICE_PASSWORD_PATH=$R8S_SECRETS_PATH/modular-service-pass
LM_RESPONSE_PATH=$R8S_SECRETS_PATH/lm-response
LM_API_LINK_PATH=$R8S_SECRETS_PATH/lm-link

R8S_ENVS_PATH=$R8S_SECRETS_PATH/r8s.env

MODULAR_CLI_PATH=$R8S_ARTIFACTS_PATH/modular_cli.tar.gz
GENERATE_RANDOM_ENVS_SCRIPT_PATH=$R8S_ARTIFACTS_PATH/generate_random_envs.py


# Functions
ensure_in_path() {
  if [[ ":$PATH:" == *":$1:"* ]]; then
    echo "$1 is found in user's PATH"
  else
    echo "Adding $1 to user's PATH"
    export PATH=$PATH:$1
  fi
}
generate_password() { python3 $GENERATE_RANDOM_ENVS_SCRIPT_PATH; }

get_imds_token () {
  duration="10"  # must be an integer
  if [ -n "$1" ]; then
    duration="$1"
  fi
  curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: $duration"
}
account_id() { curl -s curl -s -H "X-aws-ec2-metadata-token: $(get_imds_token)" http://169.254.169.254/latest/dynamic/instance-identity/document | jq -r ".accountId"; }
user_exists() { id "$1" &>/dev/null; }


install_modular_cli() {
  if pip freeze | grep modular-cli > /dev/null; then
    echo "Modular cli is already installed. Try: syndicate --help"
  else
    echo "Installing modular-cli"
    MODULAR_CLI_ENTRY_POINT=syndicate pip3 install --user --break-system-packages "$MODULAR_CLI_PATH"
  fi
}

initialize_system() {
  # creates:
  # - non-system admin users for Optimizer & Modular Service
  # - license entity based on LM response
  # - customer based on LM response
  # - tenant within the customer which represents this AWS account
  # - entity that represents defect dojo installation

  source "$R8S_ENVS_PATH"
  ensure_in_path "$HOME/.local/bin"

  install_modular_cli

  echo "Logging in to modular-cli"
  syndicate setup --username admin --password "$MODULAR_API_INIT_PASSWORD" --api_path http://127.0.0.1:8085 --json
  syndicate login --json

  echo "Logging in to Optimizer using system user"
  syndicate r8s configure --api_link http://optimizer:8000/r8s --json
  syndicate r8s login --username SYSTEM_ADMIN --password "$R8S_SYSTEM_USER_PASSWORD" --json

  echo "Logging in to Modular Service using system user"
  syndicate admin configure --api_link http://modular-service:8040/dev --json
  syndicate admin login --username system_user --password "$MODULAR_SERVICE_SYSTEM_USER_PASSWORD" --json


  lm_response=$(cat $LM_RESPONSE_PATH)
  customer_name=$(echo $lm_response | jq ".customer_name" -r)


  echo "Generating passwords for modular-service and optimizer non-system users"
  generate_password > $MODULAR_SERVICE_PASSWORD_PATH
  generate_password > $R8S_PASSWORD_PATH
  chmod o-r $R8S_PASSWORD_PATH $MODULAR_SERVICE_PASSWORD_PATH

  echo "Creating modular service customer and its user"
  syndicate admin signup --username "$MODULAR_SERVICE_USERNAME" --password $(sudo cat $MODULAR_SERVICE_PASSWORD_PATH) --customer_name "$customer_name" --customer_display_name "$customer_name" --customer_admin admin@example.com --json

  echo "Activating all aws regions in modular service"
  for r in $AWS_REGIONS;
  do
    echo "Activating $r"
    syndicate admin region activate --maestro_name "$r" --native_name "$r" -c AWS --json
  done


  echo "Creating optimizer customer user"
  LM_API_LINK=$(cat $LM_API_LINK_PATH)
  stage=$(basename $LM_API_LINK)
  host=$(dirname $LM_API_LINK)
  syndicate r8s setting config add --host $host --port 443 --protocol "HTTPS" --stage $stage --json

  syndicate r8s setting client add --key_id $(echo $lm_response | jq ".private_key.key_id" -r) --algorithm $(echo $lm_response | jq ".private_key.algorithm" -r) --private_key $(echo $lm_response | jq ".private_key.value" -r) --format "PEM" --b64encoded --json
  syndicate r8s register --username "$R8S_USERNAME" --password $(sudo cat $R8S_PASSWORD_PATH) --role_name admin_role --customer_id "$customer_name" --json


  echo "Logging in as customer users"
  syndicate admin login --username $MODULAR_SERVICE_USERNAME --password $(sudo cat $MODULAR_SERVICE_PASSWORD_PATH) --json
  syndicate r8s login --username $R8S_USERNAME --password $(sudo cat $R8S_PASSWORD_PATH) --json


  log "Setting up Licensed Application"
  output=$(syndicate r8s application licenses add --customer_id "$customer_name" --description "$customer_name application" --cloud "AWS" --tenant_license_key $(echo $lm_response | jq ".tenant_license_key" -r) --json)
  echo $output
  licensed_application_id=$(get_application_id "$output")
  echo $licensed_application_id

  log "Setting up Licensed Parent"
  syndicate r8s parent add --application_id "$licensed_application_id" --description "$customer_name parent" --scope SPECIFIC --tenant "$(account_id)" --json

  log "Setting up Metrics storage"
  syndicate r8s storage add --storage_name input_storage --type DATA_SOURCE --bucket_name r8s-metrics --json

  log "Setting up Scan results storage"
  syndicate r8s storage add --storage_name output_storage --type STORAGE --bucket_name r8s-results --json

  log "Setting up RIGHTSIZER Application"
  syndicate r8s application add --customer_id "$customer_name" --description "$customer_name application" --input_storage input_storage --output_storage output_storage --username "foo" --password "foo" --host "0.0.0.0" --port 8000 --protocol HTTP --json
}


if [ -z "$init_system" ] && [ -z "$target_user" ]; then
  exit_badly "Either --system or --user must be specified"
fi

if [ -n "$init_system" ]; then
  expected=$(stat -c '%U' /usr/local/r8s/)  # maybe use `id -un 1000`
  given=$(whoami)
  if [ "$expected" != "$given" ]; then
    exit_badly "System configuration can be performed only by '$expected' user. Given '$given'"
  fi
  if [ -f $R8S_PASSWORD_PATH ]; then
    exit_badly "Optimizer was already initialized. Cannot do that again"
  fi
  echo "Initializing Optimizer"
  initialize_system
  echo "Done"
  exit 0
fi

# target_user must exist here
test -n "$r8s_username"; _username=$?
test -n "$r8s_password"; _password=$?
if [ "$(( _username ^ _password ))" -eq 1 ]; then
  echo "--r8s-username and --r8s-password must be specified together" >&2
  exit 1
fi

test -n "$admin_username"; _username=$?
test -n "$admin_password"; _password=$?
if [ "$(( _username ^ _password ))" -eq 1 ]; then
  echo "--admin-username and --admin-password must be specified together" >&2
  exit 1
fi

echo "Initializing Optimizer for user $target_user"
if user_exists "$target_user"; then
  echo "User already exists"
else
  echo "User does not exist. Creating"
  sudo useradd --create-home --shell /bin/bash --user-group "$target_user" || exit_badly "Could not create a user"
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
sudo su - "$target_user" <<EOF
MODULAR_CLI_ENTRY_POINT=syndicate pip3 install --user --break-system-packages "$MODULAR_CLI_PATH"
EOF

# TODO fix this hack with jq. It's a kludge because modular-api return valid JSON if it succeeds and just text if it fails and always returns 0 status code
sudo docker exec modular-api ./modular.py user describe --username "$target_user" --json | jq

if [ $? -ne 0 ]; then
  echo "Creating new modular-api user"
  new_password="$(generate_password)"
  sudo docker exec modular-api ./modular.py user add --username "$target_user" --group admin_group --password "$new_password"
  sudo su - "$target_user" <<EOF
  echo "Logging in to modular-cli"
  ~/.local/bin/syndicate setup --username "$target_user" --password "$new_password" --api_path http://127.0.0.1:8085 --json
  ~/.local/bin/syndicate login --json
EOF
else
  echo "Modular api user has been initialized before"
fi


if [ -n "$r8s_username" ]; then
  echo "Logging in to Optimizer"
  sudo su - "$target_user" <<EOF
  ~/.local/bin/syndicate r8s configure --api_link http://optimizer:8000/api --json
  ~/.local/bin/syndicate r8s login --username "$r8s_username" --password "$r8s_password" --json
EOF
fi

if [ -n "$admin_username" ]; then
  echo "Logging in to Modular Service"
  sudo su - "$target_user" <<EOF
  ~/.local/bin/syndicate admin configure --api_link http://modular-service:8040/dev --json
  ~/.local/bin/syndicate admin login --username "$admin_username" --password "$admin_password" --json
EOF
fi
echo "Done"
exit 0