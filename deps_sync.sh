#!/bin/bash
source .venv/bin/activate
uv pip sync requirements.txt
uv pip install .