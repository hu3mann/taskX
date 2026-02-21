FROM python:3.12-slim
WORKDIR /app
RUN useradd -m -r -s /bin/false taskx && chown -R taskx:taskx /app
COPY dist/*.whl .
RUN pip install --no-cache-dir *.whl
USER taskx
ENTRYPOINT ["taskx"]
