"""Comic Fuz API client for authentication and content retrieval."""

import os
import re
import json
import logging
from typing import List, Tuple, Optional
from urllib.request import Request, urlopen
from getpass import getpass
import requests

from .proto import fuz_pb2
from .models import Chapter


class FuzAPIClient:
    """Client for interacting with Comic Fuz API."""

    API_HOST = "https://api.comic-fuz.com"
    IMG_HOST = "https://img.comic-fuz.com"
    WEB_HOST = "https://comic-fuz.com"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/96.0.4664.55 Safari/537.36 Edg/96.0.1054.34"
    )
    COOKIE_TEMPLATE = "is_logged_in=true; fuz_session_key="

    def __init__(self, token: str = ""):
        self.token = token
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": self.USER_AGENT})

    def sign_in(self, email: str, password: str) -> str:
        """Sign in with email and password, return session token."""
        body = fuz_pb2.SignInRequest()
        body.deviceInfo.deviceType = fuz_pb2.DeviceInfo.DeviceType.BROWSER
        body.email = email
        body.password = password

        url = f"{self.API_HOST}/v1/sign_in"
        req = Request(url, body.SerializeToString(), method="POST")

        with urlopen(req) as r:
            res = fuz_pb2.SignInResponse()
            res.ParseFromString(r.read())

            if not res.success:
                raise RuntimeError("Login failed")

            for header_name in r.headers:
                if header_name.lower() != 'set-cookie':
                    continue
                m = re.search(r'fuz_session_key=([^;]+)', r.headers[header_name])
                if m:
                    self.token = m.group(1)
                    logging.info("Logged in")
                    return self.token

        raise RuntimeError("Failed to extract token from response")

    def check_token(self, token: str) -> bool:
        """Check if a token is valid and return user email if logged in."""
        url = f"{self.API_HOST}/v1/web_mypage"
        headers = {
            "user-agent": self.USER_AGENT,
            "cookie": self.COOKIE_TEMPLATE + token
        }
        req = Request(url, headers=headers, method="POST")

        try:
            with urlopen(req) as r:
                res = fuz_pb2.WebMypageResponse()
                res.ParseFromString(r.read())
                if res.mailAddress:
                    logging.info("Logged in as: %s", res.mailAddress)
                    return True
        except Exception as e:
            logging.debug(f"Token validation failed: {e}")

        return False

    def get_session(self, token_file: str = "", user_email: str = "", password: str = "") -> str:
        """Get or create a session token."""
        if not token_file and not user_email:
            logging.info("No authentication - accessing free content only")
            self.token = ""
            return ""

        if token_file and os.path.exists(token_file):
            with open(token_file) as f:
                token = f.read().strip()
            if self.check_token(token):
                self.token = token
                return token
            logging.debug("Saved token invalid, re-authenticating")

        if not user_email:
            user_email = input("Email: ")
        if not password:
            password = getpass("Password: ")

        token = self.sign_in(user_email, password)

        if token_file:
            with open(token_file, "w") as f:
                f.write(token)

        return token

    def _api_request(self, path: str, body: bytes) -> bytes:
        """Make a generic API request with authentication."""
        url = self.API_HOST + path
        headers = {"user-agent": self.USER_AGENT}

        if self.token:
            headers["cookie"] = self.COOKIE_TEMPLATE + self.token

        req = Request(url, body, headers, method="POST")
        with urlopen(req) as r:
            return r.read()

    def get_manga_viewer(self, chapter_id: int) -> fuz_pb2.MangaViewerResponse:
        """Get manga chapter data."""
        body = fuz_pb2.MangaViewerRequest()
        body.deviceInfo.deviceType = fuz_pb2.DeviceInfo.DeviceType.BROWSER
        body.chapterId = chapter_id
        body.viewerMode.imageQuality = fuz_pb2.ViewerMode.ImageQuality.HIGH

        res_data = self._api_request("/v1/manga_viewer", body.SerializeToString())
        response = fuz_pb2.MangaViewerResponse()
        response.ParseFromString(res_data)
        return response

    def get_book_viewer(self, book_id: int) -> fuz_pb2.BookViewer2Response:
        """Get book data."""
        body = fuz_pb2.BookViewer2Request()
        body.deviceInfo.deviceType = fuz_pb2.DeviceInfo.DeviceType.BROWSER
        body.bookIssueId = book_id
        body.viewerMode.imageQuality = fuz_pb2.ViewerMode.ImageQuality.HIGH

        res_data = self._api_request("/v1/book_viewer_2", body.SerializeToString())
        response = fuz_pb2.BookViewer2Response()
        response.ParseFromString(res_data)
        return response

    def get_magazine_viewer(self, magazine_id: int) -> fuz_pb2.MagazineViewer2Response:
        """Get magazine data."""
        body = fuz_pb2.MagazineViewer2Request()
        body.deviceInfo.deviceType = fuz_pb2.DeviceInfo.DeviceType.BROWSER
        body.magazineIssueId = magazine_id
        body.viewerMode.imageQuality = fuz_pb2.ViewerMode.ImageQuality.HIGH

        res_data = self._api_request("/v1/magazine_viewer_2", body.SerializeToString())
        response = fuz_pb2.MagazineViewer2Response()
        response.ParseFromString(res_data)
        return response

    def get_chapters_from_manga(self, manga_id: int) -> Tuple[List[Chapter], Optional[str]]:
        """Scrape a manga's page and return (chapters, manga title)."""
        url = f"{self.WEB_HOST}/manga/{manga_id}"
        logging.debug(f"Fetching manga page: {url}")

        resp = self._session.get(url)
        if resp.status_code != 200:
            raise RuntimeError(f'Failed to get manga page. HTTP {resp.status_code}')

        match = re.search(r'__NEXT_DATA__" type="application/json">({.*?})</script>', resp.text)
        if not match:
            raise RuntimeError('Could not find manga data in page')

        data = json.loads(match.group(1))
        page_props = data.get('props', {}).get('pageProps', {})

        manga_data = page_props.get('manga', {})
        manga_title = manga_data.get('title') or manga_data.get('mangaName') if manga_data else None

        all_chapters = []
        for group in page_props.get('chapters', []):
            for ch in group.get('chapters', []):
                all_chapters.append(Chapter(
                    chapter_id=ch.get('chapterId'),
                    manga_id=manga_id,
                    chapter_main_name=ch.get('chapterMainName', ''),
                    chapter_sub_name=ch.get('chapterSubName', ''),
                    price=ch.get('pointConsumption', {}).get('amount', 0) or 0,
                ))

        logging.info(f"Found {len(all_chapters)} chapters for manga {manga_id}")
        return all_chapters, manga_title
