FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Cortex Code CLI (Linux x64/arm64, headless via -p flag).
# The install script prompts for Podman (sandbox feature) which requires a TTY.
# The CLI itself installs successfully before that prompt, so we suppress the exit code.
RUN curl -LsS https://ai.snowflake.com/static/cc-scripts/install.sh | sh || true
ENV PATH="/root/.local/bin:${PATH}"
# Fail the build immediately if the binary didn't land on PATH.
# Catches silent install failures before the image is pushed to the registry.
RUN ls /root/.local/bin/cortex || (echo "ERROR: cortex CLI binary not found after install" && exit 1)

RUN pip install --no-cache-dir snowflake-connector-python[secure-local-storage]

COPY aeo_spcs_runner.py /app/aeo_spcs_runner.py
COPY aeo_spcs_interactive.py /app/aeo_spcs_interactive.py
COPY transcript_capture.py /app/transcript_capture.py

WORKDIR /app

# RUN_MODE=interactive  → single-question runner (triggered by SiS via EXECUTE JOB SERVICE)
# RUN_MODE=batch        → 16-question batch runner (default, used by setup-snowhouse.sql)
CMD ["sh", "-c", "if [ \"$RUN_MODE\" = 'interactive' ]; then python -u /app/aeo_spcs_interactive.py; else python -u /app/aeo_spcs_runner.py; fi"]
