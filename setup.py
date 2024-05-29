from setuptools import setup

setup(
    name="expyro",
    version="0.0.1",
    description="A minimal library to keep track of experiments.",
    url="https://github.com/lukashaverbeck/expyro",
    author="Lukas Haverbeck",
    license="MIT",
    packages=["expyro"],
    requires=["tyro", "matplotlib"]
)
