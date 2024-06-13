from pathlib import Path

from setuptools import setup, find_packages

setup(
    name="expyro",
    version="0.0.1",
    description="A minimal library to keep track of experiments.",
    long_description=Path("README.md").read_text(),
    long_description_content_type="text/markdown",
    url="https://github.com/lukashaverbeck/expyro",
    author="Lukas Haverbeck",
    license="MIT",
    python_requires=">=3.11",
    requires=["tyro", "matplotlib"],
    packages=find_packages(),
    include_package_data=True,
)