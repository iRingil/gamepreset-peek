"""Box art of the games, downloaded once into a disk cache."""

import hashlib
import os
from pathlib import Path
from typing import Any

from loguru import logger

from app.config import COVER_WIDTH, COVERS_DIR, NV_GAME_ART_URL
from app.infra.http_client import HttpClient, HttpClientError

__all__: tuple[str, ...] = ("CoverCache",)


class CoverCache:
    """Keeps the box art of each game as a file named after its URL, so a new picture of a game gets a new file.

    A URL the image server no longer answers is looked up again by the game's application id; the picture of the
    current URL is kept under the old URL's name, where it is found until a database update brings the new URL.

    A file is written beside its place and renamed into it, so a broken download never leaves a half picture."""

    def __init__(self, *, http: HttpClient, folder: Path = COVERS_DIR) -> None:
        """
        Use the given cache folder.

        :param http: HTTP client the downloads go through
        :param folder: cache folder, created on the first download
        """
        self._http: HttpClient = http
        self._folder: Path = folder

    def get(self, *, url: str, app_id: str | None) -> Path:
        """
        Get the picture of a URL, downloading it unless it is cached.

        :param url: box art URL from the database
        :param app_id: application id of the game, to find the current URL when this one fails
        :return: the picture file
        """
        path: Path = self._folder / f"{hashlib.sha256(url.encode(encoding='utf-8')).hexdigest()[:32]}.jpg"
        if path.is_file():
            return path
        try:
            body: bytes = self._download(url=url)
        except HttpClientError as error:
            body = self._download_current(url=url, app_id=app_id, error=error)
        self._folder.mkdir(parents=True, exist_ok=True)
        temp: Path = path.with_suffix(".download")
        temp.write_bytes(data=body)
        os.replace(src=temp, dst=path)
        logger.debug("Cached the cover {} as {}", url, path)
        return path

    def _download(self, *, url: str) -> bytes:
        """
        Download a picture at the width of the cover column.

        :param url: box art URL
        :return: the JPEG file
        """
        # The image server resizes and converts a picture on request.
        return self._http.get_bytes(url=f"{url};f=jpg;w={COVER_WIDTH}")

    def _download_current(self, *, url: str, app_id: str | None, error: HttpClientError) -> bytes:
        """
        Download the picture of an application's current box art URL after its URL from the database failed.

        :param url: the failed URL
        :param app_id: application id of the game
        :param error: the failure of the URL, raised again when there is no other URL
        :return: the JPEG file
        """
        if app_id is None:
            raise error
        current: str = self._current_url(app_id=app_id)
        if current in ("", url):
            raise error
        logger.info("Cover {} answered HTTP {}, using {}", url, error.status, current)
        return self._download(url=current)

    def _current_url(self, *, app_id: str) -> str:
        """
        Ask the image service for the current box art URL of an application.

        :param app_id: application id
        :return: the URL, empty when the service doesn't know the application or has no box art for it
        """
        # A real service region: a made-up one gets a cut-down list of applications.
        query: str = (
            f'{{ apps(vpcId: "NP-AMS-08", language: "en_US", appIds: ["{app_id}"]) '
            "{ items { id images { GAME_BOX_ART } } } }"
        )
        answer: Any = self._http.get_json(url=NV_GAME_ART_URL, params={"query": query})
        data: Any = answer.get("data") if isinstance(answer, dict) else None
        apps: Any = data.get("apps") if isinstance(data, dict) else None
        items: Any = apps.get("items") if isinstance(apps, dict) else None
        for item in items if isinstance(items, list) else []:
            images: Any = item.get("images") if isinstance(item, dict) and item.get("id") == app_id else None
            url: Any = images.get("GAME_BOX_ART") if isinstance(images, dict) else None
            if isinstance(url, str) and url:
                return url
        logger.info("No current box art for application {}", app_id)
        return ""
