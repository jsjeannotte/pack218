#!/bin/bash
source .venv/bin/activate
python3 -m uvicorn pack218.app:app --env-file .env --host 0.0.0.0 --port 8001 --workers 1