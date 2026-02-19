FROM python:3.12-slim@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
WORKDIR /app
RUN useradd -m -r -s /bin/false taskx && chown -R taskx:taskx /app
COPY dist/*.whl .
RUN pip install --no-cache-dir *.whl
USER taskx
ENTRYPOINT ["taskx"]
