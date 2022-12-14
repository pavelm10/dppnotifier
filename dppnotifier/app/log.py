import logging


def init_logger():
    """
    initializes basic console logger
    """
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s %(name)s [%(levelname)s]: %(message)s'
    )
    handler.setFormatter(formatter)
    if len(logger.handlers) == 0:
        logger.addHandler(handler)

    logging.getLogger('botocore').setLevel(logging.WARNING)
