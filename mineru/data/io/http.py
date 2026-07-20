# Copyright (c) Opendatalab. All rights reserved.

import io

import requests

from .base import IOReader, IOWriter

DEFAULT_HTTP_TIMEOUT_SECONDS = 60.0


class HttpReader(IOReader):

    def __init__(self, timeout: float = DEFAULT_HTTP_TIMEOUT_SECONDS) -> None:
        self.timeout = timeout

    def read(self, url: str) -> bytes:
        """Read the file.

        Args:
            path (str): file path to read

        Returns:
            bytes: the content of the file
        """
        response = requests.get(
            url,
            timeout=self.timeout,
            allow_redirects=False,
        )
        return response.content

    def read_at(self, path: str, offset: int = 0, limit: int = -1) -> bytes:
        """Not Implemented."""
        raise NotImplementedError


class HttpWriter(IOWriter):
    def __init__(self, timeout: float = DEFAULT_HTTP_TIMEOUT_SECONDS) -> None:
        self.timeout = timeout

    def write(self, url: str, data: bytes) -> None:
        """Write file with data.

        Args:
            path (str): the path of file, if the path is relative path, it will be joined with parent_dir.
            data (bytes): the data want to write
        """
        files = {'file': io.BytesIO(data)}
        response = requests.post(
            url,
            files=files,
            timeout=self.timeout,
            allow_redirects=False,
        )
        assert 300 > response.status_code and response.status_code > 199
