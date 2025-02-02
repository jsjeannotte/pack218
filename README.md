# pack218
Simple website for CubScout Pack 218

## Local setup

```shell
$ python3 -m venv .venv
$ source .venv/bin/activate
$ uv pip compile requirements.in -o requirements.txt
$ uv pip install -r requirements.txt
$ pycharm .
```

To just add dependencies and re-sync the venv:

```shell
$ source .venv/bin/activate
$ uv pip compile requirements.in -o requirements.txt
$ uv pip compile tests/requirements.in -o tests/requirements.txt
$ uv pip sync tests/requirements.txt
```

## References

- NiceGUI: https://nicegui.io/documentation
- NiceCRUD: https://github.com/Dronakurl/nicecrud
- 
