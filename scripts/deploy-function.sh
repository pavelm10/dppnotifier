#!/usr/bin/env bash

set -e

aws lambda update-function-code \
  --function-name dpp_notifier \
  --zip-file fileb://dppnotifier_package.zip
