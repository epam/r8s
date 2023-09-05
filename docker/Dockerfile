FROM public.ecr.aws/docker/library/python:3.8 as compile-image

WORKDIR /build

# cachable part
COPY docker/requirements.txt docker/requirements.txt
RUN pip install --user -r ./docker/requirements.txt && \
    useradd r8s

# end cachable part
COPY docker docker


FROM public.ecr.aws/docker/library/python:3.8-slim AS build-image

ENV PATH=/root/.local/bin:$PATH
COPY --from=compile-image /root/.local /root/.local
COPY --from=compile-image /build/docker /home/r8s/

WORKDIR /home/r8s
