FROM public.ecr.aws/docker/library/python:3.8

ARG mcdm=maestro-common-domain-model

COPY $mcdm/mcdm_sdk ../mcdm_sdk/
COPY r8s r8s/

WORKDIR /r8s

RUN for file in $(find . -type f -name "*.txt"); do if grep -q "git+ssh://" $file; then sed -i '/git+ssh:\/\//d' $file && echo "Removed git+ssh:// from $PATH_TO_FILE" $file; fi; done && \
    pip install --upgrade pip && \
    for d in src/lambdas/*; do if [ -d "$d" ]; then pip install -r "$d/requirements.txt"; fi; done && \
    pip install -r docker/requirements.txt && \
    pip install -r src/exported_module/requirements.txt && \
    pip install -r scripts/requirements.txt && \
    pip install -r src/requirements.txt && \
    pip install ../mcdm_sdk/ && \
    rm -rf r8s/.git

ENV AWS_REGION=eu-central-1 \
    SERVICE_MODE=docker \
    PYTHONPATH=/r8s/:/r8s/src/:$PYTHONPATH \
    mcdm_service_mode=docker
#    VENV_PATH=/r8s/docker/.executor_venv/bin/python \
#    EXECUTOR_PATH=/r8s/docker/executor.py \
#    CUSTOMER_NAME=$CUSTOMER_NAME

WORKDIR /r8s/src

#CMD python3 main.py