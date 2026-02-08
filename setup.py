from setuptools import setup, find_packages

setup(
    name="delta-agent",
    version="0.1.0",
    packages=find_packages(),
    py_modules=["main"],
    install_requires=[
        "aiohttp",
        "requests",
        "pydantic",
        "python-dotenv",
        "colorama",
        "restrictedpython",
    ],
    entry_points={
        "console_scripts": [
            "delta=main:main",
        ],
    },
)
