#!/usr/bin/env bash

set -e

SHA=`git rev-parse HEAD`

aws lambda update-function-code \
  --function-name dpp_notifier \
  --zip-file fileb://dppnotifier_package.zip \
  --output json

aws lambda publish-version \
    --function-name dpp_notifier \
    --description $SHA \
    --output json
