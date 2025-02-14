from setuptools import setup

setup(
    name="pack218",
    versioning="distance",          # Optional, would activate tag-based versioning
    setup_requires="setupmeta",
    # Include the static files in the package
    package_data={"pack218": ["images/*"]},
)
