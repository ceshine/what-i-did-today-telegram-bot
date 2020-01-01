from setuptools import setup, find_packages

from widt.version import __version__

setup(
    name="widt",
    version=__version__,
    author="Ceshine Lee",
    author_email="ceshine@ceshine.net",
    description="What I Did Today telegram bot",
    license="Apache License, Version 2.0",
    url="",
    packages=['widt'],
    install_requires=[],
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8"
    ],
    keywords=""
)
