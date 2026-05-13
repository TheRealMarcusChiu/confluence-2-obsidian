import urllib3
import requests
from urllib.parse import urljoin


PAGE_EXPAND = "ancestors,body.storage,version,metadata.labels,history.lastUpdated,space"
PAGE_LIMIT = 50
ATTACHMENT_LIMIT = 100


class ConfluenceClient:
    def __init__(self, base_url: str, username: str, password: str, verify_ssl: bool = False):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.verify = verify_ssl
        if not verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def _api(self, path: str) -> str:
        return f"{self.base_url}/rest/api/{path.lstrip('/')}"

    def list_pages(self, space_key: str):
        start = 0
        while True:
            params = {
                "spaceKey": space_key,
                "type": "page",
                "expand": PAGE_EXPAND,
                "start": start,
                "limit": PAGE_LIMIT,
            }
            r = self.session.get(self._api("content"), params=params, timeout=60)
            r.raise_for_status()
            data = r.json()
            results = data.get("results", [])
            for page in results:
                yield page
            if len(results) < PAGE_LIMIT:
                return
            start += PAGE_LIMIT

    def list_attachments(self, page_id: str):
        start = 0
        while True:
            params = {"start": start, "limit": ATTACHMENT_LIMIT}
            r = self.session.get(
                self._api(f"content/{page_id}/child/attachment"),
                params=params,
                timeout=60,
            )
            r.raise_for_status()
            data = r.json()
            results = data.get("results", [])
            for att in results:
                yield att
            if len(results) < ATTACHMENT_LIMIT:
                return
            start += ATTACHMENT_LIMIT

    def download_attachment(self, attachment: dict) -> bytes:
        download_path = attachment.get("_links", {}).get("download", "")
        if not download_path:
            raise ValueError(f"No download link for attachment {attachment.get('id')}")
        url = urljoin(self.base_url + "/", download_path.lstrip('/'))
        r = self.session.get(url, timeout=120)
        r.raise_for_status()
        return r.content

    def page_web_url(self, page: dict) -> str:
        webui = page.get("_links", {}).get("webui", "")
        if webui:
            return urljoin(self.base_url + "/", webui.lstrip('/'))
        return ""
