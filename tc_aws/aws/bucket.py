# coding: utf-8

# Copyright (c) 2015, thumbor-community
# Use of this source code is governed by the MIT license that can be
# found in the LICENSE file.

from .session import get_session
from tornado_botocore import Botocore
from tornado.concurrent import run_on_executor
from thumbor.utils import logger
from thumbor.engines import BaseEngine


class Bucket(object):
    """
    This handles all communication with AWS API
    """

    _bucket = None
    _region = None
    _endpoint = None
    _local_cache = dict()

    def __init__(self, bucket, region, endpoint):
        """
        Constructor
        :param string bucket: The bucket name
        :param string region: The AWS API region to use
        :param string endpoint: A specific endpoint to use
        :return: The created bucket
        """
        self._bucket = bucket
        self._region = region
        self._endpoint = endpoint

    @run_on_executor
    def get(self, path, callback=None):
        """
        Returns object at given path
        :param string path: Path or 'key' to retrieve AWS object
        :param callable callback: Callback function for once the retrieval is done
        """
        my_session = get_session(self._endpoint is not None)
        session = Botocore(
            service="s3",
            region_name=self._region,
            operation="GetObject",
            session=my_session,
            endpoint_url=self._endpoint,
        )
        session.call(
            callback=callback,
            Bucket=self._bucket,
            Key=self._clean_key(path),
        )

    @run_on_executor
    def get_url(self, path, method="GET", expiry=3600, callback=None):
        """
        Generates the presigned url for given key & methods
        :param string path: Path or 'key' for requested object
        :param string method: Method for requested URL
        :param int expiry: URL validity time
        :param callable callback: Called function once done
        """
        session = get_session(self._endpoint is not None)
        client = session.create_client("s3", region_name=self._region, endpoint_url=self._endpoint)

        url = client.generate_presigned_url(
            ClientMethod="get_object",
            Params={
                "Bucket": self._bucket,
                "Key": self._clean_key(path),
            },
            ExpiresIn=expiry,
            HttpMethod=method,
        )

        callback(url)

    @run_on_executor
    def put(
        self,
        path,
        data,
        metadata={},
        reduced_redundancy=False,
        encrypt_key=False,
        callback=None,
    ):
        """
        Stores data at given path
        :param string path: Path or 'key' for created/updated object
        :param bytes data: Data to write
        :param dict metadata: Metadata to store with this data
        :param bool reduced_redundancy: Whether to reduce storage redundancy or not?
        :param bool encrypt_key: Encrypt data?
        :param callable callback: Called function once done
        """
        storage_class = "REDUCED_REDUNDANCY" if reduced_redundancy else "STANDARD"
        content_type = BaseEngine.get_mimetype(data) or "application/octet-stream"

        args = dict(
            callback=callback,
            Bucket=self._bucket,
            Key=self._clean_key(path),
            Body=data,
            ContentType=content_type,
            Metadata=metadata,
            StorageClass=storage_class,
        )

        if encrypt_key:
            args["ServerSideEncryption"] = "AES256"

        my_session = get_session(self._endpoint is not None)
        session = Botocore(
            service="s3",
            region_name=self._region,
            operation="PutObject",
            session=my_session,
            endpoint_url=self._endpoint,
        )

        session.call(**args)

    @run_on_executor
    def delete(self, path, callback=None):
        """
        Deletes key at given path
        :param string path: Path or 'key' to delete
        :param callable callback: Called function once done
        """
        my_session = get_session(self._endpoint is not None)
        session = Botocore(
            service="s3",
            region_name=self._region,
            operation="DeleteObject",
            session=my_session,
            endpoint_url=self._endpoint,
        )
        session.call(
            callback=callback,
            Bucket=self._bucket,
            Key=self._clean_key(path),
        )

    def _clean_key(self, path):
        logger.debug("Cleaning key: {path}".format(path=path))
        key = path
        while "//" in key:
            logger.debug(key)
            key = key.replace("//", "/")

        if "/" == key[0]:
            key = key[1:]

        logger.debug("Cleansed key: {key}".format(key=key))
        return key
