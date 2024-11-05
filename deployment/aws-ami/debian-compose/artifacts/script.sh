#!/bin/bash

# Constants
LM_API_LINK="https://lm.syndicate.team"
R8S_RELEASE=3.10.0

R8S_LOCAL_PATH=/usr/local/r8s
R8S_ARTIFACTS_PATH=$R8S_LOCAL_PATH/artifacts
R8S_SECRETS_PATH=$R8S_LOCAL_PATH/secrets

LM_RESPONSE_FILENAME=lm-response
LM_API_LINK_FILENAME=lm-link

R8S_ENVS_FILENAME=r8s.env

R8S_IMAGE_FILENAME=r8s.tar.gz
MODULAR_SERVICE_IMAGE_FILENAME=modular-service.tar.gz
MODULAR_API_IMAGE_FILENAME=modular-api.tar.gz


R8S_COMPOSE_FILENAME=compose.yaml

GENERATE_RANDOM_ENVS_SCRIPT_FILENAME=generate_random_envs.py

FIRST_USER=$(getent passwd 1000 | cut -d : -f 1)

# Functions
log() { logger -s "$1"; }
log_err() { logger -s -p user.err "$1"; }
get_imds_token () {
  duration="10"  # must be an integer
  if [ -n "$1" ]; then
    duration="$1"
  fi
  curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: $duration"
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

if [ -f $R8S_LOCAL_PATH/success ]; then
  log "Not the first run. Exiting"
  exit 0
else
  log "The first run. Configuring Optimizer"
fi

# Prerequisite
log "Installing docker and other necessary packages"
sudo DEBIAN_FRONTEND=noninteractive apt update -y
sudo DEBIAN_FRONTEND=noninteractive apt upgrade -y
sudo DEBIAN_FRONTEND=noninteractive apt install -y git jq python3-pip unzip locales-all

# Add Docker's official GPG key: from https://docs.docker.com/engine/install/debian/
sudo DEBIAN_FRONTEND=noninteractive apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
# Add git apt repo
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo DEBIAN_FRONTEND=noninteractive apt update -y
sudo DEBIAN_FRONTEND=noninteractive apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin


log "Creating temp directory"
mkdir r8s-build-temp-dir/ && cd r8s-build-temp-dir/
mkdir artifacts/
mkdir secrets/

log "Pulling artifacts"
wget -O optimizer-artifacts.zip "https://github.com/epam/r8s/releases/download/$R8S_RELEASE/optimizer-ami-artifacts.linux-$(dpkg --print-architecture).zip"
unzip optimizer-artifacts.zip -d artifacts/
cd artifacts/

log "Loading docker images from artifacts"
sudo docker load -i $MODULAR_API_IMAGE_FILENAME
sudo docker load -i $MODULAR_SERVICE_IMAGE_FILENAME
sudo docker load -i $R8S_IMAGE_FILENAME
sudo docker load -i $DEFECT_DOJO_DJANGO_IMAGE_FILENAME
sudo docker load -i $DEFECT_DOJO_NGINX_IMAGE_FILENAME


# TODO maybe remove these steps. It depends.
sudo docker image tag localhost/m3-modular-admin:latest m3-modular-admin:latest
sudo docker image tag localhost/modular-service:latest modular-service:latest
sudo docker image tag localhost/r8s-k8s:latest r8s-k8s:latest


log "Generating random passwords for docker compose"
python3 $GENERATE_RANDOM_ENVS_SCRIPT_FILENAME --optimizer > ../secrets/$R8S_ENVS_FILENAME
source ../secrets/$R8S_ENVS_FILENAME


log "Starting optimizer docker compose"
sudo docker compose --project-directory ./ --file $R8S_COMPOSE_FILENAME --env-file ../secrets/$R8S_ENVS_FILENAME --profile modular-service --profile optimizer --profile modular-api up -d


log "Going to make request to license manager"
lm_response=$(request_to_lm)
code=$?
if [ $code -ne 0 ];
then
  log_err "Unsuccessful response from the license manager"
  exit 1
fi
lm_response=$(echo "$lm_response" | jq --indent 0 ".items[0]")
echo "$lm_response" > ../secrets/$LM_RESPONSE_FILENAME
echo $LM_API_LINK > ../secrets/$LM_API_LINK_FILENAME
log "License information was received"


log "Copying artifacts to $R8S_LOCAL_PATH"
log "Making $FIRST_USER an owner of generated secrets"
sudo mkdir -p $R8S_LOCAL_PATH

cd ..
sudo cp -R secrets/ $R8S_SECRETS_PATH
sudo cp -R artifacts/ $R8S_ARTIFACTS_PATH
sudo cp artifacts/r8s-init.sh /usr/local/bin/r8s-init
sudo chmod +x /usr/local/bin/r8s-init
sudo chmod +x $R8S_ARTIFACTS_PATH/$GENERATE_RANDOM_ENVS_SCRIPT_FILENAME
sudo chown -R $FIRST_USER:$FIRST_USER $R8S_LOCAL_PATH
sudo chmod -R o-r $R8S_SECRETS_PATH

cd ..
log "Cleaning temp directory"
rm -rf r8s-build-temp-dir/

log "Cleaning apt cache"
sudo apt clean

# Lock
sudo touch $R8S_LOCAL_PATH/success
sudo chmod 000 $R8S_LOCAL_PATH/success
