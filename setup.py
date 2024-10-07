[build-system]
requires = ["setuptools>=42", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "yachecker"
version = "1.0.2"
description = "YAC: Yes Another Checker"
readme = "README.md"
authors = [
    { name = "Ali Emara", email = "ali.emara175@gmail.com" }
]
license = { text = "MIT" }
homepage = "https://github.com/hithmast/YAC.git"
keywords = ["login", "checker", "security", "automation"]
classifiers = [
    "Programming Language :: Python :: 3",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
]

dependencies = [
    "requests",
    "argparse",
    "urllib3"
]

[project.urls]
Source = "https://github.com/hithmast/YAC"
Documentation = "https://github.com/hithmast/YAC#readme"

[tool.setuptools.packages.find]
where = ["yac"]

