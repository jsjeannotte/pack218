# FROM ghcr.io/astral-sh/uv:python3.12-bookworm
FROM ubuntu:latest

# The installer requires curl (and certificates) to download the release archive
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates build-essential libpq-dev

# Download the latest installer
ADD https://astral.sh/uv/install.sh /uv-installer.sh
# OR `curl -LsSf https://astral.sh/uv/install.sh | sh` in the shell

# Run the installer then remove it
RUN sh /uv-installer.sh && rm /uv-installer.sh
# Ensure the installed binary is on the `PATH`
ENV PATH="/root/.local/bin/:$PATH"

# Get Rust
RUN curl https://sh.rustup.rs -sSf | bash -s -- -y
RUN echo 'source $HOME/.cargo/env' >> $HOME/.bashrc
# Ensure the installed binary is on the `PATH`
ENV PATH="/root/.cargo/bin:$PATH"

# Using uv, install python
RUN uv python install 3.11

# Install the venv for the app
COPY . /app
RUN uv venv --python 3.11 /venv
RUN VIRTUAL_ENV=/venv uv pip install -r /app/requirements.txt
ENV PYTHONPATH="${PYTHONPATH}:/app"
WORKDIR /app
CMD /venv/bin/python3 -m uvicorn pack218.app:app --env-file /app/.env --host 0.0.0.0 --port 8001 --workers 1
