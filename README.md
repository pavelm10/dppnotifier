# DPP Notifier

## TODO

- unittests
- docstring
- readme

## Introduction

TODO

## Web Scrapper

TODO

## Amazon Dynamo DB

TODO

## Notifiers

### Amazon SES

To move out of sandbox follow the
[link](https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html).

### WhatsApp

- [send message](https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-messages)
- [message templates](https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-message-templates)

#### Setup never expires WhatsApp Cloud API access token

Login to your Facebook developer account and choose the WhatsApp app and then
go to the Business settings page. You will see the System users under the
section of Users on the left sidebar. Click the Add button and you will get
the pop-up window. Enter the user name and choose the admin as the system
user role.

Now, your new system user should be created. Click on the Add Asserts on the
current page(System user page) the pop-up will appear.
Choose App>Select App Name>Full control option & click save changes button.

Now, click on the “WhatsApp Account” on the left sidebar and then select the
WhatsApp business app and click the “Add people” button. Popup will appear,
choose the recently created system user and check the full control and then
click the Assign button.

Now, go back again to the system users page and select the recently created
system user from the list and then click the “Generate new token” button.

Pop up will appear, choose the business app from the dropdown and make sure
the whatsapp_business_management and whatsapp_business_messaging must be
checked, if not then click on the checkbox and click the
“Generate token” button.

The token should be generated at this time. Now, this token will not expire
and live forever until and unless you do not click the revoke token button.
You can use this token in the API instead of a temporary access token.

### Telegram

- [telegram bots](https://core.telegram.org/bots)
- token from the bot used in the URI
- get `chat_id`:
  - each user shall send `/start` message to `@RawDataBot` to get the `chat_id`

## Configuration

### Environment variables

Mandatory environment variables:
- `AWS_SENDER_EMAIL` - `AWS SES` service email name that is used to send email
notifications.
- `AWS_PROFILE` - `AWS` profile used for email notifications and DB access

All these variables have a default values, which can be overridden by defining
these environment variables:
- `EVENTS_TABLE` - name of the events table in the Dynamo DB
- `SUBSCRIBERS_TABLE` - name of the subscribers table in the Dynamo DB
- `WHATSAPP_TEMPLATE` - name of the WhatsApp messaging template

Optional environment variables without any default values:
- `WHATSAPP_CRED_PATH` - path to the WhatsApp credential file, if not provided
then the `WhatsApp Notifier` will not be enabled.
- `TELEGRAM_CRED_PATH` - path to the Telegram credential file, if not provided
then the `Telegram Notifier` will not be enabled.

## AWS Lambda

- Authentication via [Lambda Execution Role](https://docs.aws.amazon.com/lambda/latest/dg/lambda-intro-execution-role.html)
- [Deployment](https://docs.aws.amazon.com/lambda/latest/dg/python-package.html)
- [Env.vars. configuration](https://docs.aws.amazon.com/lambda/latest/dg/configuration-envvars.html)

- To use `aws cli` add `aws user access id` and `secret key` to the
`aws configure` for a use that should manage the lambda function
- Add this user to the `lambda function > Configuration > Permissions > `
`Resource-based policy statements`. You must know the principal:
`arn:aws:iam::[user_id]:user/[user_name]`.
Select action `lambda:UpdateFunctionCode`.
- In `Code > Runtime Settings` set `Handler` to
`dppnotifier.app.app.run_job`
- Ensure the `execution role` created to run the function has `invokeFunction`
right.
- No need to specify `AWS_PROFILE` env.var.
- To create a package run:
```
cd .venv/lib/python3.9/site-packages
zip -r ../../../../dppnotifier_package.zip .
cd ../../../../
zip -g dppnotifier_package.zip dppnotifier/app
```
- To create/update lambda function run:
```
aws lambda update-function-code \
  --function-name dpp_notifier \
  --zip-file fileb://dppnotifier_package.zip
```
- To invoke the function run:
```
aws lambda invoke --function-name dpp_notifier out --log-type Tail
```