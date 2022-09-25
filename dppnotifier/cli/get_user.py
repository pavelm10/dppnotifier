import argparse
import logging

from dppnotifier.app.db import DynamoSubscribersDb
from dppnotifier.app.log import init_logger
from dppnotifier.app.types import Notifiers

_LOGGER = logging.getLogger(__name__)


if __name__ == '__main__':
    init_logger()
    argp = argparse.ArgumentParser()
    argp.add_argument('-n', '--notifier', required=True, help='notifier type')
    argp.add_argument(
        '-t', '--table', required=False, default='dpp-notifier-recepients'
    )

    pargs = argp.parse_args()
    notifier = pargs.notifier
    table = pargs.table

    db = DynamoSubscribersDb(table)
    subs = db.get_subscriber(Notifiers(notifier))
    for sub in subs:
        _LOGGER.info(sub)
