#!/bin/bash

# shellcheck disable=SC2034
LM_API_LINK="https://lm-qa.syndicate.team" # todo change to PROD url
GITHUB_REPO=epam/r8s
FIRST_USER=$(getent passwd 1000 | cut -d : -f 1)
R8S_LOCAL_PATH=/usr/local/r8s
LOG_PATH=/var/log/r8s-init.log

get_imds_token () { curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 300"; }
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
      log "Failed to send signal to Cloud Formation"
    fi
  else
    log "Not sending signal to Cloud Formation because CF_STACK_NAME is not set"
  fi
}
on_exit() { local status=$?; [ "$status" -ne 0 ] && send_cf_signal "FAILURE"; }
trap on_exit EXIT

# here we load possible envs provided from outside.
if user_data="$(get_from_metadata /user-data/)"; then
  # shellcheck disable=SC1090
  source <(echo "$user_data")
fi


log() { echo "[INFO] $(date) $1" >> $LOG_PATH; }

if [ -f $R8S_LOCAL_PATH/success ]; then
  log "Syndicate RightSizer was already initialized. Skipping"
  exit 0
fi

log "Installing jq and curl"
sudo apt update -y && sudo apt install -y jq curl

#RIGHTSIZER_RELEASE="$(curl -fLs "https://api.github.com/repos/$GITHUB_REPO/releases/latest" | jq -r '.tag_name')"
RIGHTSIZER_RELEASE="3.11.0"
if [ -z "$RIGHTSIZER_RELEASE" ]; then
  log "Could not find latest release"
  exit 1
fi

log "Executing ami-initialize from release $RIGHTSIZER_RELEASE"
# shellcheck disable=SC1090
source <(wget -O - "https://github.com/epam/r8s/releases/download/$RIGHTSIZER_RELEASE/ami-initialize.sh")

modular_api_pod_name=$(kubectl get pods -n default -l app.kubernetes.io/name=modular-api -o jsonpath='{.items[0].metadata.name}')
log "Waiting for modular api pod to be Running: ${modular_api_pod_name}"
kubectl wait --for=condition=ready --timeout=300s pod/${modular_api_pod_name}


# will be downloaded by line above
log "Executing r8s-init --system"
sudo -u "$FIRST_USER" r8s-init --system | sudo tee -a $LOG_PATH >/dev/null

log "Sending CF Signal resource request with SUCCESS status"
send_cf_signal "SUCCESS"

log "Creating $R8S_LOCAL_PATH/success"
sudo touch $R8S_LOCAL_PATH/success
sudo chmod 000 $R8S_LOCAL_PATH/success