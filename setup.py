"""
Setup script for Austin City Excel Ingestion Tool.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

# Read requirements
requirements = (this_directory / "requirements.txt").read_text().splitlines()

setup(
    name="austin-excel-ingestion",
    version="0.1.0",
    author="Rodrigo Botello",
    description="A Python tool for ingesting and parsing Excel documents",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "austin-excel=src.main:app",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Text Processing :: Markup",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    keywords="excel parsing ingestion pandas",
    project_urls={
        "Bug Reports": "https://github.com/rodBotellosa/austin-city-excel-ingestion/issues",
        "Source": "https://github.com/rodBotellosa/austin-city-excel-ingestion",
    },
) 