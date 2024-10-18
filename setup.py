from setuptools import setup, find_packages

setup(
    name="yachecker",
    version="1.0.2",
    description="YAC: Yes Another Checker",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Ali Emara",
    author_email="ali.emara175@gmail.com",
    url="https://github.com/hithmast/YAC",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    keywords=["login", "checker", "security", "automation"],
    license="MIT",
    packages=find_packages(where="yac"),
    python_requires=">=3.6",
    install_requires=[
        "requests",
        "argparse",
        "urllib3"
    ],
    project_urls={
        "Source": "https://github.com/hithmast/YAC",
        "Documentation": "https://github.com/hithmast/YAC#readme",
    },
)
