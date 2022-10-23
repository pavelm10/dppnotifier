import logging
import os
from io import BytesIO

import boto3

from dppnotifier.app.constants import AWS_REGION
from dppnotifier.app.utils import utcnow_localized

_LOGGER = logging.getLogger(__name__)


def store_html(html_content: bytes, bucket_name: str) -> None:
    """Stores the HTML content to the AWS S3 bucket.

    Parameters
    ----------
    html_content : bytes
        Scrapped HTML content
    bucket_name : str
        Name of the HTML historization bucket
    """
    profile = os.getenv('AWS_PROFILE')
    now = utcnow_localized().strftime('%Y_%m_%dT%H_%M_%S')
    object_name = f'{now}.html'
    data = BytesIO(html_content)

    session = boto3.Session(profile_name=profile)
    s3_client = session.resource('s3', region_name=AWS_REGION)
    s3_client.Bucket(bucket_name).upload_fileobj(data, object_name)
    _LOGGER.info('Stored current HTML of the source URL')
