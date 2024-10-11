from setuptools import setup, find_packages

setup(
    name="vcolor",
    version="1.0.0",
    description="Command-line tool to colorize video frames using deep learning models.",
    author="Your Name",
    author_email="your.email@example.com",
    packages=find_packages(include=["colorizers", "colorizers.*"]),
    scripts=["vcolor.py"],
    entry_points={
        "console_scripts": [
            "vcolor = vcolor:cli",
        ],
    },
    include_package_data=True,
    package_data={
        "colorizers": ["*.py"],
    },
)
