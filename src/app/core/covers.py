"""Box art of the games, downloaded once into a disk cache."""

import hashlib
import os
from pathlib import Path

from loguru import logger

from app.config import COVER_WIDTH, COVERS_DIR
from app.infra.http_client import HttpClient

__all__: tuple[str, ...] = ("CoverCache",)


class CoverCache:
    """Keeps the box art of each game as a file named after its URL, so a new picture of a game gets a new file.

    A file is written beside its place and renamed into it, so a broken download never leaves a half picture."""

    def __init__(self, *, http: HttpClient, folder: Path = COVERS_DIR) -> None:
        """
        Use the given cache folder.

        :param http: HTTP client the downloads go through
        :param folder: cache folder, created on the first download
        """
        self._http: HttpClient = http
        self._folder: Path = folder

    def get(self, *, url: str) -> Path:
        """
        Get the picture of a URL, downloading it unless it is cached.

        :param url: box art URL from the database
        :return: the picture file
        """
        path: Path = self._folder / f"{hashlib.sha256(url.encode(encoding='utf-8')).hexdigest()[:32]}.jpg"
        if path.is_file():
            return path
        # The image server resizes and converts a picture on request.
        body: bytes = self._http.get_bytes(url=f"{url};f=jpg;w={COVER_WIDTH}")
        self._folder.mkdir(parents=True, exist_ok=True)
        temp: Path = path.with_suffix(".download")
        temp.write_bytes(data=body)
        os.replace(src=temp, dst=path)
        logger.debug("Cached the cover {} as {}", url, path)
        return path
