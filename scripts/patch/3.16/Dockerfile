FROM public.ecr.aws/docker/library/python:3.14 AS builder

COPY src/requirements.txt /tmp/requirements.txt
RUN pip install --prefix=/install --no-cache-dir \
    --disable-pip-version-check -r /tmp/requirements.txt

FROM public.ecr.aws/docker/library/python:3.14-slim

ARG PATCH_VERSION=3.16
ARG USERNAME=r8s

RUN groupadd --gid=1337 $USERNAME && \
    useradd --system --uid=1001 --gid=1337 --no-create-home $USERNAME

COPY --from=builder /install /usr/local
COPY --chown=$USERNAME:$USERNAME src /src
COPY --chown=$USERNAME:$USERNAME scripts/patch/$PATCH_VERSION/main.py /patch/main.py

WORKDIR /patch
USER $USERNAME
ENV SERVICE_MODE=docker \
    PYTHONPATH=/src \
    PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "/patch/main.py"]
