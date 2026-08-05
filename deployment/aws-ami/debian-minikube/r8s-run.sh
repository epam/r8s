#!/bin/bash

set -eo pipefail

get_imds_token() { curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 300"; }
get_from_metadata() {
  local token="$2"
  [ -z "$token" ] && token="$(get_imds_token)"
  curl -sf -H "X-aws-ec2-metadata-token: $token" "http://169.254.169.254/latest$1"
}

cf_signal() {
  # first parameter is either "SUCCESS" or "FAILURE". The second one is stack name
  local url query region instance_id doc sig token
  declare -A region_to_endpoint
  region_to_endpoint["eu-isoe-west-1"]="https://cloudformation.eu-isoe-west-1.cloud.adc-e.uk/"
  region_to_endpoint["us-iso-east-1"]="https://cloudformation.us-iso-east-1.c2s.ic.gov/"
  region_to_endpoint["us-iso-west-1"]="https://cloudformation.us-iso-west-1.c2s.ic.gov/"
  region_to_endpoint["us-isob-east-1"]="https://cloudformation.us-isob-east-1.sc2s.sgov.gov/"
  region_to_endpoint["us-isof-east-1"]="https://cloudformation.us-isof-east-1.csp.hci.ic.gov/"
  region_to_endpoint["us-isof-south-1"]="https://cloudformation.us-isof-south-1.csp.hci.ic.gov/"
  region_to_endpoint["cn-north-1"]="https://cloudformation.cn-north-1.amazonaws.com.cn/"
  region_to_endpoint["cn-northwest-1"]="https://cloudformation.cn-northwest-1.amazonaws.com.cn/"

  token="$(get_imds_token)"
  region="$(get_from_metadata "/dynamic/instance-identity/document" "$token" | jq -r ".region")"
  doc="$(get_from_metadata "/dynamic/instance-identity/document" "$token" | base64 -w 0)"
  sig="$(get_from_metadata "/dynamic/instance-identity/signature" "$token" | tr -d '\n')"
  instance_id="$(get_from_metadata "/meta-data/instance-id" "$token")"

  if [ -n "${region_to_endpoint[$region]}" ]; then
    url="${region_to_endpoint[$region]}"
  else
    url="https://cloudformation.$region.amazonaws.com/"
  fi
  query="Action=SignalResource&LogicalResourceId=SyndicateRightSizerInstance&StackName=$2&UniqueId=$instance_id&Status=$1&ContentType=JSON&Version=2010-05-15"
  curl -sf -X GET --header 'Accept: application/json' --header "Authorization: CFN_V1 $doc:$sig" --header "User-Agent: CloudFormation Tools" "$url?$query"
}

send_cf_signal() {
  if [ -n "$CF_STACK_NAME" ]; then
    log "Sending $1 signal to CloudFormation"
    if ! cf_signal "$1" "$CF_STACK_NAME"; then
      log_err "Failed to send signal to Cloud Formation"
    fi
  else
    log "Not sending signal to Cloud Formation because CF_STACK_NAME is not set"
  fi
}
handle_error() {
  local exit_code=$1 line_number=$2
  log_err "Error (exit code ${exit_code}) on line ${line_number}"
  if [[ ${#FUNCNAME[@]} -gt 2 ]]; then
    log_err "Call stack:"
    for ((i=1; i<${#FUNCNAME[@]}-1; i++)); do
      log_err "  ${FUNCNAME[$i]}() at ${BASH_SOURCE[$i+1]:-?}:${BASH_LINENO[$i]}"
    done
  fi
  exit "$exit_code"
}
trap 'handle_error $? $LINENO' ERR

on_exit() {
  local status=$?
  [ "$status" -ne 0 ] && send_cf_signal "FAILURE"
}
trap on_exit EXIT

# here we load possible envs provided from outside.
if user_data="$(get_from_metadata /user-data/)"; then
  # shellcheck disable=SC1090
  source <(echo "$user_data")
fi

# these can be provided from outside
export GITHUB_REPO="${GITHUB_REPO:-epam/r8s}"
export R8S_LOCAL_PATH="${R8S_LOCAL_PATH:-/usr/local/r8s}"
export LOG_PATH="${LOG_PATH:-/var/log/r8s-init.log}"
export FIRST_USER="${FIRST_USER:-$(getent passwd 1000 | cut -d: -f1)}"
export LM_API_LINK="${LM_API_LINK:-https://lm.syndicate.team}"

log() { echo "[INFO] $(date) $1" >>"$LOG_PATH"; }
log_err() { echo "[ERROR] $(date) $1" >>"$LOG_PATH"; }

if [ -f "$R8S_LOCAL_PATH/success" ]; then
  log "Syndicate RightSizer was already initialized. Skipping"
  exit 0
fi

log "-----------------------------------------------------"
log "Initializing Syndicate Rightsizer for the first time"
log "-----------------------------------------------------"
log "Creating ~/.local/bin for $FIRST_USER"
sudo -u "$FIRST_USER" mkdir -p "$(getent passwd "$FIRST_USER" | cut -d: -f6)/.local/bin" || true
log "Adding user $FIRST_USER to docker group"
sudo groupadd docker || true
sudo usermod -aG docker "$FIRST_USER" || true

log "Installing jq and curl"
sudo apt update -y && sudo apt install -y jq curl

if [ -z "$RIGHTSIZER_RELEASE" ]; then
  log "Going to resolve latest release from GitHub api"
  _retries=5
  _delay=5
  for _i in $(seq 1 "$_retries"); do
    _tag="$(curl -fLs "https://api.github.com/repos/$GITHUB_REPO/releases/latest" | jq -r '.tag_name // empty')"
    if [ -n "$_tag" ] && [ "$_tag" != "null" ]; then
      export RIGHTSIZER_RELEASE="$_tag"
      break
    fi
    log "Could not resolve latest release (attempt $_i/$_retries). Retrying in ${_delay}s..."
    sleep "$_delay"
    _delay=$((_delay * 2))
  done
fi
if [ -z "$RIGHTSIZER_RELEASE" ] || [ "$RIGHTSIZER_RELEASE" = "null" ]; then
  log_err "Could not find latest release after retries. GitHub API may be rate-limited"
  exit 1
fi
log "Using Syndicate RightSizer release: $RIGHTSIZER_RELEASE"

if [ -n "$ALLOW_DRAFT_RELEASE" ] && [ -z "$GITHUB_TOKEN" ]; then
  log_err "GITHUB_TOKEN must be set when ALLOW_DRAFT_RELEASE is enabled"
  exit 1
fi

log "Downloading ami-initialize.sh from release $RIGHTSIZER_RELEASE"
ami_initialize="$(mktemp)"
if [ -n "$ALLOW_DRAFT_RELEASE" ]; then
  _asset_url="$(curl -fLs \
    -H 'X-GitHub-Api-Version: 2022-11-28' -H 'Accept: application/vnd.github+json' \
    -H "Authorization: Bearer $GITHUB_TOKEN" \
    "https://api.github.com/repos/$GITHUB_REPO/releases?per_page=100" \
    | jq -er --arg tag "$RIGHTSIZER_RELEASE" \
        '.[] | select(.tag_name == $tag) | .assets[] | select(.name == "ami-initialize.sh") | .url')" \
    || { log_err "ami-initialize.sh asset not found for release $RIGHTSIZER_RELEASE"; rm -f "$ami_initialize"; exit 1; }
  curl -fLs \
    -H "Authorization: Bearer $GITHUB_TOKEN" -H 'X-GitHub-Api-Version: 2022-11-28' \
    -H 'Accept: application/octet-stream' -o "$ami_initialize" "$_asset_url" \
    || { log_err "Failed to download ami-initialize.sh"; rm -f "$ami_initialize"; exit 1; }
else
  wget -q -O "$ami_initialize" "https://github.com/$GITHUB_REPO/releases/download/$RIGHTSIZER_RELEASE/ami-initialize.sh" \
    || { log_err "Failed to download ami-initialize.sh"; rm -f "$ami_initialize"; exit 1; }
fi

{
  # shellcheck disable=SC1090
  source "$ami_initialize"
} 2>&1 | sudo tee -a "$LOG_PATH" >/dev/null
rm "$ami_initialize"

modular_api_pod_name=$(kubectl get pods -n default -l app.kubernetes.io/name=modular-api -o jsonpath='{.items[0].metadata.name}')
log "Waiting for modular api pod to be Running: ${modular_api_pod_name}"
kubectl wait --for=condition=ready --timeout=300s "pod/${modular_api_pod_name}"

log "Executing r8s-init --system"
sudo -EH -u "$FIRST_USER" r8s-init --system 2>&1 | sudo tee -a "$LOG_PATH" >/dev/null

send_cf_signal "SUCCESS"
log "Creating $R8S_LOCAL_PATH/success"
sudo touch "$R8S_LOCAL_PATH/success"
sudo chmod 000 "$R8S_LOCAL_PATH/success"
