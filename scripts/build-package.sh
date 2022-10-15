#!/usr/bin/env bash

set -e

SHA=`git rev-parse HEAD`
SHORT_SHA=${SHA::8}
PACKAGE_NAME=dppnotifier_package
PACKAGE_NAME_FULL=${PACKAGE_NAME}_${SHORT_SHA}.zip

if [ -f ${PACKAGE_NAME}_* ]; then
    rm -rf ${PACKAGE_NAME}_*.zip
fi

rm -rf .venv
poetry env use 3.9.14
poetry install --no-dev
cd .venv/lib/python3.9/site-packages
zip -r ../../../../$PACKAGE_NAME_FULL .
cd ../../../../
zip -g -r $PACKAGE_NAME_FULL dppnotifier/app
zip -g -r $PACKAGE_NAME_FULL secrets
