import logging


def init_logger(name: str) -> logging.Logger:
    """
    initializes basic console logger
    :param name: (str) name of the logger
    :return: (logging.Logger) the actual logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(message)s')
    handler.setFormatter(formatter)
    if len(logger.handlers) == 0:
        logger.addHandler(handler)
    return logger
