import argparse
import logging

from dppnotifier.app.db import DynamoSubscribersDb
from dppnotifier.app.log import init_logger
from dppnotifier.app.types import Notifiers, Subscriber

_LOGGER = logging.getLogger(__name__)


def main():
    init_logger()

    argp = argparse.ArgumentParser()
    argp.add_argument('-u', '--user', required=True, help='user name')
    argp.add_argument(
        '-r',
        '--uri',
        required=True,
        help='email address, whatsapp id, etc. of the user',
    )
    argp.add_argument('-n', '--notifier', required=True, help='notifier type')
    argp.add_argument(
        '-l', '--lines', required=False, help='list of lines, comma separated'
    )
    argp.add_argument(
        '-t', '--table', required=False, default='dpp-notifier-recepients'
    )

    pargs = argp.parse_args()
    user = pargs.user
    uri = pargs.uri
    lines = pargs.lines
    if lines is None:
        lines = ()
    else:
        lines = lines.split(',')
    notifier = pargs.notifier
    table = pargs.table

    subscriber = Subscriber(
        notifier=Notifiers(notifier), uri=uri, lines=lines, user=user
    )
    db_client = DynamoSubscribersDb(table_name=table)
    db_client.add_subscriber(subscriber)
    _LOGGER.info('Added subscriber %s', subscriber)


if __name__ == '__main__':
    main()
