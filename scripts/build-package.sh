#!/usr/bin/env bash

set -e

PACKAGE_NAME=dppnotifier_package.zip

if [ -f ${PACKAGE_NAME} ]; then
    rm -rf $PACKAGE_NAME
fi

rm -rf .venv
pyenv local 3.9.10
poetry install --no-dev
cd .venv/lib/python3.9/site-packages
zip -r ../../../../$PACKAGE_NAME .
cd ../../../../
zip -g -r $PACKAGE_NAME dppnotifier/app
zip -g -r $PACKAGE_NAME secrets
