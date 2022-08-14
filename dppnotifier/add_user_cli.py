from dppnotifier.db import DynamoSubscribersDb
from dppnotifier.types import Notifiers, Recepient


def main():
    import argparse

    argp = argparse.ArgumentParser()
    argp.add_argument('-u', '--user', required=True, help='user name')
    argp.add_argument(
        '-r',
        '--uri',
        required=True,
        help='email address, whatsapp id, etc. of the user',
    )
    argp.add_argument('-n', '--notifier', required=True, help='notifier type')

    pargs = argp.parse_args()
    user = pargs.user
    uri = pargs.uri
    notifier = pargs.notifier

    recepient = Recepient(notifier=Notifiers(notifier), uri=uri, user=user)
    db_client = DynamoSubscribersDb(table_name='dpp-notifier-recepients')
    db_client.add_recepient(recepient)


if __name__ == '__main__':
    main()
