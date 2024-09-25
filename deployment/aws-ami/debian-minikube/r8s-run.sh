#!/bin/bash

# shellcheck disable=SC2034
LM_API_LINK="https://lm-qa.syndicate.team" # todo change to PROD url
GITHUB_REPO=epam/r8s
FIRST_USER=$(getent passwd 1000 | cut -d : -f 1)
R8S_LOCAL_PATH=/usr/local/r8s
LOG_PATH=/var/log/r8s-init.log

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
kubectl wait --for=condition=Running --timeout=300s "pod/${modular_api_pod_name}"


# will be downloaded by line above
log "Executing r8s-init --system"
sudo -u "$FIRST_USER" r8s-init --system | sudo tee -a $LOG_PATH >/dev/null

log "Creating $R8S_LOCAL_PATH/success"
sudo touch $R8S_LOCAL_PATH/success
sudo chmod 000 $R8S_LOCAL_PATH/success