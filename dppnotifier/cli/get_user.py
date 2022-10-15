import argparse
import logging

from dppnotifier.app.db import DynamoSubscribersDb
from dppnotifier.app.dpptypes import Notifiers
from dppnotifier.app.log import init_logger

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
    subs = db.get_subscribers(Notifiers(notifier))
    for sub in subs:
        _LOGGER.info(sub)
