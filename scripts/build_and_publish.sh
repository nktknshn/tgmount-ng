#!/bin/bash

# ASK FOR VERSION

python setup.py sdist &&
twine upload dist/* &&
rm -rf build/ dist/ tgmount.egg-info/
