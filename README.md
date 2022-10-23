# DPP Notifier

## Introduction

The purpose of the application is to notify users (subscribers) about sudden
traffic events in the public transport system (PTS) in Prague (Czech Republic).
The events are for example delays of trams, or sudden outage of a metro line,
and so on. The reason why this application was developed is that the
public transport system provider in Prague provides these notifications
on their web page as well as in the mobile application, but the user cannot
set a filter of which lines she is interested in, i.e. the user either gets
all notifications or none. Clearly this is very inconvenient as during normal
working day there are 20+ on average traffic events that the user would receive
the notification for, but most of them are irrelevant. The developer of the
mobile phone application is not planning to add the filtering feature, hence
this application emerged.

## Architecture

![Architecture](/docs/architecture.svg "App Architecture")

## Web Scrapper

The PTS provider posts each traffic event on their web page:
https://pid.cz/mimoradnosti/

The job periodically scraps the web page for all the current traffic events.

## Amazon Dynamo DB

### Events table

The found events are updated/inserted into the Amazon Dynamo DB table which
holds the event:
- `event ID`
- `active` - 0/1
- `start datetime`
- `end datetime`
- `lines` - affected lines
- `message` - message describing the event
- `url` - link to the event's web page

The event is updated only if there is a change to the event.

### Subscribers table

The table holds the records of the users/subscribers that wants to receive the
notifications. Each record contains:
- `notifier type` - see below
- `user name` - name of the user
- `uri` - e.g. email, phone number, etc.
- `lines` - list of lines the user wants to receive notifications for. If empty
then the use will receive notification for every new event.

## Notifiers

Currently, 3 types of notifiers are supported:
- `email` - using `AWS SES` service for sending email
- `whatsapp` - using `WhatsApp API` for sending the message
- `telegram` - using `Telegram API` for sending the message

### Amazon SES

To move out of sandbox follow the
[link](https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html).

### WhatsApp

- [send message](https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-messages)
- [message templates](https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-message-templates)

The `Lambda` build requires the JSON credential file be in `/secrets`.
The expected format of the `WhatsApp` JSON file is:
```JSON
{
  "token": "whatsapp_token",
  "phone_id": "phone_id_given_by_meta",
  "account_id": "account_id_given_by_meta"
}
```

#### Setup never expiring WhatsApp Cloud API access token

Login to your Facebook developer account and choose the `WhatsApp app` and then
go to the `Business settings` page. You will see the `System users` under the
section of `Users` on the left sidebar. Click the `Add` button and you will get
the pop-up window. Enter the `user name` and choose the `admin` as the system
user role.

Now, your new system user should be created. Click on the `Add Asserts` on the
current page (System user page) the pop-up will appear.
Choose `App>Select App Name>Full control option` & click `save changes` button.

Now, click on the `WhatsApp Account` on the left sidebar and then select the
`WhatsApp business` app and click the `Add people` button. Popup will appear,
choose the recently created system user and check the full control and then
click the `Assign` button.

Now, go back again to the `system users` page and select the recently created
system user from the list and then click the `Generate new token` button.

Pop up will appear, choose the business app from the dropdown and make sure
the `whatsapp_business_management` and `whatsapp_business_messaging` must be
checked, if not then click on the checkbox and click the `Generate token`
button.

The token should be generated at this time. Now, this token will not expire
and live forever until and unless you do not click the revoke token button.
You can use this token in the API instead of a temporary access token.

### Telegram

- [telegram bots](https://core.telegram.org/bots)
- token from the bot used in the URI
- get `chat_id`:
  - each user shall send `/start` message to `@RawDataBot` to get the `chat_id`

The `Lambda` build requires JSON credential file to be in `/secrets`.
The expected format of the `Telegram` JSON file is:
```JSON
{
  "token": "telegram_token",
  "name": "bot_name",
  "uri": "t.me/bot_name"
}
```

## Configuration

### Environment variables

Mandatory environment variables:
- `AWS_SENDER_EMAIL` - `AWS SES` service email name that is used to send email
notifications.
- `AWS_PROFILE` - `AWS` profile used for email notifications and DB access
- `AWS_S3_RAW_DATA_BUCKET` - Name of the `AWS S3` storage bucket where to
store the HTML input data in case of parsing error or when `HISTORIZE` variable
is set.

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
- `HISTORIZE` - When set to any value the input HTML content will be stored to
`AWS_S3_RAW_DATA_BUCKET` if there is a change of the content.

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

## Deployment

To build the AWS Lambda function package run:
```
./scripts/build-package.sh
```

The script expects that the access tokens for `Telegram` and `WhatsApp` APIs
are stored in the JSON files which are put into `/secrets` folder in the root
of this repository.

- To deploy the function run:
```
./scripts/deploy-function.sh
```
- To invoke the function run:
```
aws lambda invoke --function-name dpp_notifier out --log-type Tail
```

## TODO

- unittests
- scaling to multiple AWS lambdas
