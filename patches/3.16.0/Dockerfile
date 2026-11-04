FROM python:3.12-alpine

RUN pip install --no-cache-dir pymongo==4.11.2

COPY --chmod=711 main.py /usr/local/bin/r8spatch.py

ENTRYPOINT ["python", "/usr/local/bin/r8spatch.py"]
