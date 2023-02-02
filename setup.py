#!/usr/bin/env python

from distutils.core import setup
import os

with open("README.md", "r") as fh:  # description to be used in pypi project page
    long_description = fh.read()

install_requires = [
    "telethon",
    "typing_extensions",
    "greenback",
    "aiofiles",
    "pyyaml",
    "tqdm",
    "pyfuse3",
]


def main():
    os.chdir(os.path.dirname(os.path.realpath(__file__)))

    package_path = "tgmount"
    packages = []

    for root, dirnames, filenames in os.walk(package_path):
        if "__init__.py" in filenames:
            relpath = os.path.relpath(root, os.path.dirname(package_path))
            package_name = relpath.replace(os.sep, ".")
            packages.append(package_name)

    assert packages

    setup(
        name="tgmount",
        version="1.0.1",
        description="Mount telegram messages as files",
        author="Nikita Kanashin",
        author_email="nikita@kanash.in",
        url="https://github.com/nktknshn/tgmount-ng",
        packages=packages,
        long_description=long_description,
        long_description_content_type="text/markdown",
        install_requires=install_requires,
        entry_points={"console_scripts": ["tgmount = tgmount.client:main"]},
    )


if __name__ == "__main__":
    main()
