#!/bin/bash

LOG_PATH=/var/log/r8s-init.log
ERROR_LOG_PATH=$LOG_PATH
SYNDICATE_HELM_REPOSITORY="${SYNDICATE_HELM_REPOSITORY:-https://charts-repository.s3.eu-west-1.amazonaws.com/syndicate/}"
HELM_RELEASE_NAME=rightsizer
DOCKER_VERSION='5:27.1.1-1~debian.12~bookworm'
MINIKUBE_VERSION=v1.33.1
KUBERNETES_VERSION=v1.30.0
KUBECTL_VERSION=v1.30.3
HELM_VERSION=3.15.3-1


log() { echo "[INFO] $(date) $1" >> $LOG_PATH; }
log_err() { echo "[ERROR] $(date) $1" >> $ERROR_LOG_PATH; }
# shellcheck disable=SC2120
get_imds_token () {
  duration="10"  # must be an integer
  if [ -n "$1" ]; then
    duration="$1"
  fi
  curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: $duration"
}
identity_document() { curl -s -H "X-aws-ec2-metadata-token: $(get_imds_token)" http://169.254.169.254/latest/dynamic/instance-identity/document; }
document_signature() { curl -s -H "X-aws-ec2-metadata-token: $(get_imds_token)" http://169.254.169.254/latest/dynamic/instance-identity/signature | tr -d '\n'; }
request_to_lm() { curl -s -X POST -d "{\"signature\":\"$(document_signature)\",\"document\":\"$(identity_document | base64 -w 0)\"}" "$LM_API_LINK/marketplace/rightsizer/init"; }
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
minikube_ip(){ sudo su "$FIRST_USER" -c "minikube ip"; }
enable_minikube_service() {
  sudo tee /etc/systemd/system/rightsizer-minikube.service <<EOF > /dev/null
[Unit]
Description=RightSizer minikube start up
After=docker.service

[Service]
Type=oneshot
ExecStart=/usr/bin/minikube start --profile rightsizer --force --interactive=false
ExecStop=/usr/bin/minikube stop --profile rightsizer
User=$FIRST_USER
Group=$FIRST_USER
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
  sudo systemctl enable rightsizer-minikube.service
}
upgrade_and_install_packages() {
  sudo DEBIAN_FRONTEND=noninteractive apt-get update -y
  # sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y jq curl python3-pip locales-all nginx
}
install_docker() {
  # Add Docker's official GPG key: from https://docs.docker.com/engine/install/debian/
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl
  sudo install -m 0755 -d /etc/apt/keyrings
  sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
  sudo chmod a+r /etc/apt/keyrings/docker.asc
  # Add git apt repo
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
  sudo DEBIAN_FRONTEND=noninteractive apt-get update -y
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y docker-ce="$1" docker-ce-cli="$1" containerd.io
}
install_minikube() {
  # https://minikube.sigs.k8s.io/docs/start
  log "Installing minikube"
  curl -LO "https://storage.googleapis.com/minikube/releases/$1/minikube_latest_$(dpkg --print-architecture).deb"
  sudo dpkg -i "minikube_latest_$(dpkg --print-architecture).deb" && rm "minikube_latest_$(dpkg --print-architecture).deb"
}
install_kubectl() {
  # https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/#install-kubectl-binary-with-curl-on-linux
  curl -LO "https://dl.k8s.io/release/$1/bin/linux/$(dpkg --print-architecture)/kubectl"
  curl -LO "https://dl.k8s.io/release/$1/bin/linux/$(dpkg --print-architecture)/kubectl.sha256"
  echo "$(cat kubectl.sha256) kubectl" | sha256sum --check || exit 1
  sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl && rm kubectl kubectl.sha256
}
install_helm() {
  # https://helm.sh/docs/intro/install/
  curl https://baltocdn.com/helm/signing.asc | gpg --dearmor | sudo tee /usr/share/keyrings/helm.gpg > /dev/null
  sudo apt-get install apt-transport-https --yes
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/helm.gpg] https://baltocdn.com/helm/stable/debian/ all main" | sudo tee /etc/apt/sources.list.d/helm-stable-debian.list
  sudo apt-get update
  sudo apt-get install helm="$1"
}
nginx_conf() {
  cat <<EOF
worker_processes auto;
pid /run/nginx.pid;
error_log /var/log/nginx/error.log;
# error_log /dev/null emerg;
events {
    worker_connections 1024;
}
http {
    include /etc/nginx/mime.types;
    include /etc/nginx/sites-enabled/*;
}
EOF
}
nginx_defectdojo_conf() {
  cat <<EOF
server {
    listen 80;
    location / {
        include /etc/nginx/proxy_params;
        proxy_set_header X-NginX-Proxy true;
        real_ip_header X-Real-IP;
        proxy_pass http://$(minikube_ip):32107;  # dojo
    }
}
EOF
}
nginx_minio_api_conf() {
  cat <<EOF
server {
    listen 9000;
    ignore_invalid_headers off;
    client_max_body_size 0;
    proxy_buffering off;
    proxy_request_buffering off;
    location / {
        include /etc/nginx/proxy_params;
        proxy_connect_timeout 300;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        chunked_transfer_encoding off;
        proxy_pass http://$(minikube_ip):32102; # minio api
   }
}
EOF
}
nginx_minio_console_conf() {
  cat <<EOF
server {
    listen 9001;
    ignore_invalid_headers off;
    client_max_body_size 0;
    proxy_buffering off;
    proxy_request_buffering off;
    location / {
        include /etc/nginx/proxy_params;
        proxy_set_header X-NginX-Proxy true;
        real_ip_header X-Real-IP;
        proxy_connect_timeout 300;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        # proxy_set_header Origin '';
        chunked_transfer_encoding off;
        proxy_pass http://$(minikube_ip):32103; # minio ui
   }
}
EOF
}
nginx_r8s_conf() { # check minikube r8s port
  cat <<EOF
server {
    listen 8000;
    location /r8s {
        include /etc/nginx/proxy_params;
        proxy_set_header X-Original-URI \$request_uri;
        proxy_redirect off;
        proxy_pass http://$(minikube_ip):32106/r8s;
    }
    location /ms {
        include /etc/nginx/proxy_params;
        proxy_set_header X-Original-URI \$request_uri;
        proxy_redirect off;
        proxy_pass http://$(minikube_ip):32104/dev;
    }
}
EOF
}
nginx_modular_api_conf() {
  cat <<EOF
server {
    listen 8085;
    location / {
        include /etc/nginx/proxy_params;
        proxy_redirect off;
        proxy_pass http://$(minikube_ip):32105;
    }
}
EOF
}

# $R8S_LOCAL_PATH $LM_API_LINK, $RIGHTSIZER_RELEASE, $FIRST_USER will be provided from outside
if [ -z "$R8S_LOCAL_PATH" ] || [ -z "$LM_API_LINK" ] || [ -z "$RIGHTSIZER_RELEASE" ] || [ -z "$FIRST_USER" ] || [ -z "$GITHUB_REPO" ]; then
  error_log "R8S_LOCAL_PATH=$R8S_LOCAL_PATH LM_API_LINK=$LM_API_LINK RIGHTSIZER_RELEASE=$RIGHTSIZER_RELEASE FIRST_USER=$FIRST_USER. Something is not provided"
  exit 1
fi
log "Script is executed on behalf of $(id)"

log "The first run. Configuring r8s for user $FIRST_USER"

# Prerequisite
log "Upgrading system and installing some necessary packages"
upgrade_and_install_packages

log "Installing docker $DOCKER_VERSION"
install_docker "$DOCKER_VERSION"

log "Installing minikube $MINIKUBE_VERSION"
install_minikube "$MINIKUBE_VERSION"

log "Installing kubectl $KUBECTL_VERSION"
install_kubectl "$KUBECTL_VERSION"

log "Installing helm $HELM_VERSION"
install_helm "$HELM_VERSION"

log "Adding user $FIRST_USER to docker group"
sudo usermod -aG docker "$FIRST_USER"

log "Starting minikube and installing helm releases on behalf of $FIRST_USER"
sudo su - "$FIRST_USER" <<EOF
minikube start --driver=docker --container-runtime=containerd -n 1 --force --interactive=false --memory=max --cpus=max --profile rightsizer --kubernetes-version=$KUBERNETES_VERSION
minikube profile rightsizer  # making default
kubectl create secret generic minio-secret --from-literal=username=miniouser --from-literal=password=$(generate_password)
kubectl create secret generic mongo-secret --from-literal=username=mongouser --from-literal=password=$(generate_password 30 -hex)
kubectl create secret generic vault-secret --from-literal=token=$(generate_password 30)
kubectl create secret generic rightsizer-secret --from-literal=system-password=$(generate_password 30)
kubectl create secret generic modular-api-secret --from-literal=system-password=$(generate_password 20 -hex) --from-literal=secret-key="$(generate_password 50)"
kubectl create secret generic modular-service-secret --from-literal=system-password=$(generate_password 30)
kubectl create secret generic defectdojo-secret --from-literal=secret-key="$(generate_password 50)" --from-literal=credential-aes-256-key=$(generate_password) --from-literal=db-username=defectdojo --from-literal=db-password=$(generate_password 30 -hex)

helm repo add syndicate "$SYNDICATE_HELM_REPOSITORY"
helm repo update syndicate

helm install "$HELM_RELEASE_NAME" syndicate/rightsizer --version $RIGHTSIZER_RELEASE
helm install defectdojo syndicate/defectdojo
EOF

log "Downloading artifacts"
sudo mkdir -p "$R8S_LOCAL_PATH/backups"
sudo mkdir -p "$R8S_LOCAL_PATH/releases/$RIGHTSIZER_RELEASE"
sudo wget -O "$R8S_LOCAL_PATH/releases/$RIGHTSIZER_RELEASE/modular_cli.tar.gz" "https://github.com/$GITHUB_REPO/releases/download/$RIGHTSIZER_RELEASE/modular_cli.tar.gz"  # todo get from modular-cli repo
#sudo wget -O "$R8S_LOCAL_PATH/releases/$RIGHTSIZER_RELEASE/sre_obfuscator.tar.gz" "https://github.com/$GITHUB_REPO/releases/download/$RIGHTSIZER_RELEASE/r8s_obfuscator.tar.gz" # todo add obfuscator
sudo wget -O "$R8S_LOCAL_PATH/releases/$RIGHTSIZER_RELEASE/r8s-init.sh" "https://github.com/$GITHUB_REPO/releases/download/$RIGHTSIZER_RELEASE/r8s-init.sh"
sudo cp "$R8S_LOCAL_PATH/releases/$RIGHTSIZER_RELEASE/r8s-init.sh" /usr/local/bin/r8s-init
sudo chmod +x /usr/local/bin/r8s-init
sudo chown -R $FIRST_USER:$FIRST_USER "$R8S_LOCAL_PATH"


log "Going to make request to license manager"
log "LM Api Link to be used: $LM_API_LINK"
lm_response=$(request_to_lm)
code=$?
if [ $code -ne 0 ];
then
  log_err "Unsuccessful response from the license manager: $lm_response"
  exit 1
fi
lm_response=$(echo "$lm_response" | jq --indent 0 ".items[0]")
sudo su - "$FIRST_USER" <<EOF
kubectl create secret generic lm-data --from-literal=api-link='$LM_API_LINK' --from-literal=lm-response='$lm_response'
EOF
log "License information was received"


log "Describing DefectDojo pod"
while [[ -z "$dojo_pod" ]]; do
  dojo_pod=$(sudo su "$FIRST_USER" -c "kubectl get pods" | awk '{print $1}' | grep defectdojo-initializer)
  sleep 5
done
log "Dojo pod name: $dojo_pod"

log "Getting Defect dojo password"
while [ -z "$dojo_pass" ]; do
  sleep 5
  dojo_pass=$(sudo su "$FIRST_USER" -c "kubectl logs $dojo_pod" | grep -oP "Admin password: \K\w+")
done
dojo_pass=$(base64 <<< "$dojo_pass")

sudo su - "$FIRST_USER" <<EOF
kubectl patch secret defectdojo-secret -p="{\"data\":{\"system-password\":\"$dojo_pass\"}}"
EOF
log "Defect dojo secret was saved"

log "Enabling minikube service"
enable_minikube_service

log "Configuring nginx"
sudo rm /etc/nginx/sites-enabled/*
sudo rm /etc/nginx/sites-available/*
nginx_conf | sudo tee /etc/nginx/nginx.conf > /dev/null
nginx_defectdojo_conf | sudo tee /etc/nginx/sites-available/defectdojo > /dev/null
nginx_minio_api_conf | sudo tee /etc/nginx/sites-available/minio > /dev/null
nginx_minio_console_conf | sudo tee /etc/nginx/sites-available/minio-console > /dev/null
nginx_r8s_conf | sudo tee /etc/nginx/sites-available/r8s > /dev/null  # r8s + modular-service
nginx_modular_api_conf | sudo tee /etc/nginx/sites-available/modular-api > /dev/null

sudo ln -s /etc/nginx/sites-available/defectdojo /etc/nginx/sites-enabled/
sudo ln -s /etc/nginx/sites-available/modular-api /etc/nginx/sites-enabled/
sudo ln -s /etc/nginx/sites-available/minio /etc/nginx/sites-enabled/

sudo nginx -s reload

log "Cleaning apt cache"
sudo apt-get clean
log 'Done'