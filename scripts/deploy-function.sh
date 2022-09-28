#!/usr/bin/env bash

set -e

SHA=`git rev-parse HEAD`
SHORT_SHA=${SHA::8}
PACKAGE_NAME=dppnotifier_package
PACKAGE_NAME_FULL=${PACKAGE_NAME}_${SHORT_SHA}.zip

aws lambda update-function-code \
  --function-name dpp_notifier \
  --zip-file fileb://${PACKAGE_NAME_FULL} \
  --output json \
  --no-paginate
