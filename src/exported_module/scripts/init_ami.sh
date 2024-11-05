#!/bin/bash


LM_API_LINK="https://lm.syndicate.team"


log() {
    echo "LOGGING [$(date)] $1"
}

instance_public_ipv4() {
    curl -s http://169.254.169.254/latest/meta-data/public-ipv4
}
account_id() {
    curl -s http://169.254.169.254/latest/dynamic/instance-identity/document | python3 -c "import sys,json;print(json.load(sys.stdin)['accountId'])"
}
region() {
    curl -s http://169.254.169.254/latest/dynamic/instance-identity/document | python3 -c "import sys,json;print(json.load(sys.stdin)['region'])"
}

identity_document() {
    curl -s http://169.254.169.254/latest/dynamic/instance-identity/document | base64
}
document_signature() {
    curl -s http://169.254.169.254/latest/dynamic/instance-identity/signature | tr -d '\n'
}

request_to_lm() {
    # accepts link to LM as the first argument
    curl -s -X POST -d "{\"signature\":\"$(document_signature)\",\"document\":\"$(identity_document)\"}" "$LM_API_LINK/marketplace/rightsizer/init"
}

get_customer_name() {
    echo "$1" | python3 -c "import sys,json;print(json.load(sys.stdin)['items'][0]['customer_name'])"
}
get_tenant_license_key() {
    echo "$1" | python3 -c "import sys,json;print(json.load(sys.stdin)['items'][0]['tenant_license_key'])"
}
get_key_id() {
    echo "$1" | python3 -c "import sys,json;print(json.load(sys.stdin)['items'][0]['private_key']['key_id'])"
}
get_algorithm() {
    echo "$1" | python3 -c "import sys,json;print(json.load(sys.stdin)['items'][0]['private_key']['algorithm'])"
}
get_private_key(){
    echo "$1" | python3 -c "import sys,json;print(json.load(sys.stdin)['items'][0]['private_key']['value'])"
}
get_key_format(){
    echo "$1" | python3 -c "import sys,json;print(json.load(sys.stdin)['items'][0]['private_key']['format'])"
}
get_application_id() {
    echo "$1" | python3 -c "import sys,json;print(json.load(sys.stdin)['items'][0]['application_id'])"
}

install_modular_cli() {
  if pip freeze | grep modular-cli > /dev/null; then
    echo "Modular cli is already installed. Try: syndicate --help"
  else
    echo "Installing modular-cli"
    export MODULAR_CLI_ENTRY_POINT=syndicate
    pip3 install  "/m3-modular-cli"
  fi
}

if [ $# -eq 0 ]; then
    log "No arguments are supplied. Please specify path to r8s"
    exit 1
fi

R8S_ROOT="$1"

if [ ! -d "$R8S_ROOT" ]; then
    log "$R8S_ROOT directory does not exist"
    exit 1
fi


log "Making a request to the license manager"
lm_response=$(request_to_lm $LM_API_LINK)
echo $lm_response
code=$?
if [ $code -ne 0 ];
then
  echo "Unsuccessful response from the license manager"
  echo "$lm_response"
  exit 1
fi
echo "successful"


CUSTOMER_NAME=$(get_customer_name "$lm_response")
echo "Customer: $CUSTOMER_NAME"

log "Using r8s root: $R8S_ROOT"

source "$R8S_ROOT/.venv/bin/activate"


log "Initializing Vault"
python3 $R8S_ROOT/src/exported_module/scripts/init_vault.py

log "Initializing MinIO"
python3 $R8S_ROOT/src/exported_module/scripts/init_minio.py

log "Initializing MongoDB indexes"
python3 $R8S_ROOT/src/exported_module/scripts/init_mongo.py

log "Creating system user"
login_command=$(python3 $R8S_ROOT/src/exported_module/scripts/init_system_user.py)
if [[ -n "$login_command" ]]; then
  log "Saving admin creds to file"
  echo "$login_command" | grep -E 'r8s login' >> r8s_system_user.txt
fi
echo $login_command

echo "Populating AWS Shapes/Pricing data"
python3 $R8S_ROOT/scripts/populate_aws_shapes.py --region $AWS_REGION

log "Creating customer"
python3 $R8S_ROOT/src/exported_module/scripts/init_customer.py --customer_name "$CUSTOMER_NAME"

deactivate



python3 -m venv /r8s/.r8s_venv
source /r8s/.r8s_venv/bin/activate

log "Installing modular-cli"
install_modular_cli

log "Modular-cli configuration"
syndicate setup --api_path $MODULAR_API_HOST --username $MODULAR_API_USER --password $MODULAR_API_PASSWORD

log "Modular-cli login"
syndicate login

log "Installing r8s cli"
pip install $R8S_ROOT/r8s

log "Starting rightsizer server"
$R8S_ROOT/.venv/bin/python3 $R8S_ROOT/src/main.py > /dev/null 2>&1 &
server_pid="$!"
log "Going to sleep for 5 seconds"
sleep 5  # wait till the server is up


log "Configuring r8s cli"
r8s configure --api_link http://0.0.0.0:8000/r8s
eval "$login_command"


log "Setting up LM Config setting"
stage=$(basename $LM_API_LINK)
host=$(dirname $LM_API_LINK)
r8s setting config add --host $host --stage $stage --protocol HTTPS --port 443


log "Setting up LM Client setting"
r8s setting client add --key_id "$(get_key_id "$lm_response")" --algorithm "$(get_algorithm "$lm_response")" --private_key "$(get_private_key "$lm_response")" --format "$(get_key_format "$lm_response")" --b64encoded

log "Setting up Licensed Application"
output=$(r8s application licenses add --customer_id "$CUSTOMER_NAME" --description "$CUSTOMER_NAME application" --cloud "AWS" --tenant_license_key "$(get_tenant_license_key "$lm_response")" --json)
echo $output
licensed_application_id=$(get_application_id "$output")
echo $licensed_application_id

log "Setting up Licensed Parent"
acc_id="$(account_id)"
r8s parent add --application_id "$licensed_application_id" --description "$CUSTOMER_NAME parent" --scope SPECIFIC --tenant "$acc_id" --json

log "Setting up Metrics storage"
r8s storage add --storage_name input_storage --type DATA_SOURCE --bucket_name r8s-metrics --json

log "Setting up Scan results storage"
r8s storage add --storage_name output_storage --type STORAGE --bucket_name r8s-results --json

log "Setting up RIGHTSIZER Application"
r8s application add --customer_id "$CUSTOMER_NAME" --description "$CUSTOMER_NAME application" --input_storage input_storage --output_storage output_storage --username "-" --password "-" --host "0.0.0.0" --port 8000 --protocol HTTP --json

log "Stopping r8s server"
kill $server_pid
