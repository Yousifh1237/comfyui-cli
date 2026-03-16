"""Setup script for comfyui-cli."""

from setuptools import setup, find_packages

setup(
    name="comfyui-cli",
    version="0.1.0",
    description="comfyui-cli - Command-line interface for ComfyUI",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="comfyui-cli",
    python_requires=">=3.10",
    packages=find_packages(include=["comfyui", "comfyui.*"]),
    install_requires=[
        "click>=8.0",
    ],
    entry_points={
        "console_scripts": [
            "comfyui-cli=comfyui.comfyui_cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Multimedia :: Graphics",
        "Topic :: Software Development :: Libraries",
    ],
)
