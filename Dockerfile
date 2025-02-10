FROM ghcr.io/astral-sh/uv:python3.12-bookworm
RUN ls -la /
COPY . /app
RUN uv venv --python 3.11 /venv
RUN VIRTUAL_ENV=/venv uv pip install -r /app/requirements.txt
CMD cd /app && /venv/bin/python3 -m uvicorn pack218.app:app --host 0.0.0.0 --port 8001 --workers 1
