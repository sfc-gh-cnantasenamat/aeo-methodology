FROM python:3.11-slim

RUN pip install --no-cache-dir snowflake-connector-python[secure-local-storage]

COPY aeo_spcs_runner.py /app/aeo_spcs_runner.py

WORKDIR /app

CMD ["python", "-u", "aeo_spcs_runner.py"]
