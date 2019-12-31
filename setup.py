from setuptools import setup, find_packages

from widt.version import __version__

setup(
    name="widt",
    version=__version__,
    author="Ceshine Lee",
    author_email="ceshine@ceshine.net",
    description="What I Did Today telegram bot",
    license="GLWT(Good Luck With That)",
    url="",
    packages=['widt'],
    install_requires=[],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3.6",
    ],
    keywords=""
)
