"""Safe, bounded content extraction adapters for verification requests."""

from html.parser import HTMLParser
import base64
import ipaddress
import os
from pathlib import Path
import socket
from urllib.parse import urlparse

import requests


MAX_TEXT_CHARS = 50000
MAX_DOWNLOAD_BYTES = 8 * 1024 * 1024


class ContentExtractionError(Exception):
    pass


class _VisibleTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "noscript", "template", "svg"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "noscript", "template", "svg"} and self.hidden_depth:
            self.hidden_depth -= 1

    def handle_data(self, data):
        if not self.hidden_depth and data.strip():
            self.parts.append(data.strip())

    @property
    def text(self):
        return " ".join(self.parts)


def _safe_url(url):
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ContentExtractionError("Only public HTTP or HTTPS URLs are accepted.")
    hostname = parsed.hostname.lower().rstrip(".")
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".local"):
        raise ContentExtractionError("Private network URLs are not accepted.")
    addresses = []
    try:
        addresses = [item[4][0] for item in socket.getaddrinfo(hostname, None)]
    except socket.gaierror:
        pass
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise ContentExtractionError("Private network URLs are not accepted.")
        except ValueError:
            continue
    return parsed.geturl()


def _normalise(text):
    return " ".join(str(text or "").split())[:MAX_TEXT_CHARS]


class VerificationContentExtractor:
    def __init__(self):
        self.user_agent = os.getenv(
            "REELROOTS_HTTP_USER_AGENT",
            "ReelRoots/0.1 (cultural heritage research platform)",
        )
        self.transcript_endpoint = os.getenv("TRANSCRIPT_API_URL", "").strip()
        self.ocr_endpoint = os.getenv("OCR_API_URL", "").strip()

    def extract(self, request):
        if request.input_text.strip():
            return _normalise(request.input_text), {"method": "submitted_text"}
        if request.source_file:
            return self._extract_file(request)
        if request.source_url:
            return self._extract_url(request.source_url, request.input_type)
        raise ContentExtractionError("Submit a URL, file, or text to begin verification.")

    def _extract_file(self, request):
        try:
            if request.source_file.size > MAX_DOWNLOAD_BYTES:
                raise ContentExtractionError("Uploaded files must be smaller than 8 MB.")
            with request.source_file.open("rb") as handle:
                raw = handle.read(MAX_DOWNLOAD_BYTES + 1)
        except OSError as exc:
            raise ContentExtractionError("The uploaded file could not be read.") from exc
        if len(raw) > MAX_DOWNLOAD_BYTES:
            raise ContentExtractionError("Uploaded files must be smaller than 8 MB.")
        name = Path(request.source_file.name).name.lower()
        if request.input_type == "pdf" or name.endswith(".pdf"):
            try:
                from pypdf import PdfReader
                import io
                text = " ".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(raw)).pages)
                return _normalise(text), {"method": "pdf_text", "filename": name}
            except ImportError as exc:
                raise ContentExtractionError("PDF extraction is not configured on this server.") from exc
            except Exception as exc:
                raise ContentExtractionError("The PDF could not be read as text.") from exc
        if request.input_type == "image" or name.endswith((".png", ".jpg", ".jpeg", ".webp")):
            text = self._ocr_bytes(raw, name)
            if text:
                return text, {"method": "external_ocr", "filename": name}
            return "", {"method": "image_pending_ocr", "filename": name}
        try:
            return _normalise(raw.decode("utf-8", errors="replace")), {"method": "text_file", "filename": name}
        except UnicodeDecodeError as exc:
            raise ContentExtractionError("This file format is not supported yet.") from exc

    def _extract_url(self, url, input_type):
        safe_url = _safe_url(url)
        if input_type == "video" and self.transcript_endpoint:
            try:
                response = requests.post(
                    self.transcript_endpoint,
                    json={"video_url": safe_url, "source_url": safe_url},
                    headers={"User-Agent": self.user_agent},
                    timeout=20,
                )
                response.raise_for_status()
                transcript = _normalise(response.json().get("transcript", ""))
                if transcript:
                    return transcript, {"method": "external_transcript", "source_url": safe_url}
            except (requests.RequestException, ValueError, TypeError):
                pass
            return "", {"method": "video_transcript_unavailable", "source_url": safe_url}
        try:
            response = requests.get(
                safe_url,
                headers={"User-Agent": self.user_agent},
                timeout=15,
                stream=True,
            )
            response.raise_for_status()
            _safe_url(response.url)
            content_type = response.headers.get("Content-Type", "").lower()
            raw = response.raw.read(MAX_DOWNLOAD_BYTES + 1)
        except (requests.RequestException, ContentExtractionError) as exc:
            raise ContentExtractionError("The submitted URL could not be retrieved safely.") from exc
        if len(raw) > MAX_DOWNLOAD_BYTES:
            raise ContentExtractionError("Remote content is larger than the 8 MB limit.")
        if "pdf" in content_type or safe_url.lower().endswith(".pdf"):
            try:
                from pypdf import PdfReader
                import io
                text = " ".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(raw)).pages)
                return _normalise(text), {"method": "remote_pdf_text", "source_url": safe_url}
            except Exception as exc:
                raise ContentExtractionError("The submitted PDF could not be read as text.") from exc
        if content_type.startswith("image/"):
            text = self._ocr_url(safe_url)
            if text:
                return text, {"method": "external_ocr", "source_url": safe_url}
            return "", {"method": "image_pending_ocr", "source_url": safe_url, "content_type": content_type}
        parser = _VisibleTextParser()
        parser.feed(raw.decode("utf-8", errors="replace"))
        return _normalise(parser.text), {"method": "webpage_text", "source_url": safe_url, "content_type": content_type}

    def _ocr_bytes(self, raw, filename):
        if not self.ocr_endpoint:
            return ""
        try:
            response = requests.post(
                self.ocr_endpoint,
                json={"image_base64": base64.b64encode(raw).decode("ascii"), "filename": filename},
                headers={"User-Agent": self.user_agent},
                timeout=20,
            )
            response.raise_for_status()
            return _normalise(response.json().get("text", ""))
        except (requests.RequestException, ValueError, TypeError):
            return ""

    def _ocr_url(self, url):
        if not self.ocr_endpoint:
            return ""
        try:
            response = requests.post(
                self.ocr_endpoint,
                json={"image_url": url},
                headers={"User-Agent": self.user_agent},
                timeout=20,
            )
            response.raise_for_status()
            return _normalise(response.json().get("text", ""))
        except (requests.RequestException, ValueError, TypeError):
            return ""
