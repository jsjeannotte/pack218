FROM pack218venv
ADD . /pack218baked
RUN VIRTUAL_ENV=/venv uv pip install /pack218baked
RUN mkdir -p /data
WORKDIR /data
CMD /venv/bin/python3 -m uvicorn pack218.app:app --env-file /pack218/.env --host 0.0.0.0 --port 8001 --workers 1
