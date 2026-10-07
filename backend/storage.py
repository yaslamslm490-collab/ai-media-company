"""Server-side transfer helper for durable Manus object storage."""
from __future__ import annotations

import http.client
import json
import os
import re
import ssl
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


class StorageError(RuntimeError):
    pass


class PlatformObjectStorage:
    def __init__(self, *, environ: dict[str, str] | None = None):
        env = environ if environ is not None else os.environ
        self.base_url = env.get("MANUS_API_URL", "").rstrip("/")
        self.api_key = env.get("MANUS_API_KEY", "")

    @property
    def available(self) -> bool:
        return bool(self.base_url and self.api_key)

    @staticmethod
    def _validate_key(key: str) -> None:
        if (
            not isinstance(key, str)
            or not key.isascii()
            or not re.fullmatch(r"generated-media/[A-Za-z0-9._/-]{1,180}", key)
            or any(part in {"", ".", ".."} for part in key.split("/"))
        ):
            raise StorageError("invalid_storage_key")

    def _presigned_url(self, operation: str, key: str) -> str:
        self._validate_key(key)
        if not self.available:
            raise StorageError("platform_storage_not_configured")
        query = urlencode({"path": key})
        request = Request(
            f"{self.base_url}/v1/storage/presign/{operation}?{query}",
            headers={"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"},
            method="GET",
        )
        try:
            with urlopen(request, timeout=20) as response:
                raw = response.read(64 * 1024 + 1)
            if len(raw) > 64 * 1024:
                raise StorageError("platform_storage_bad_response")
            payload = json.loads(raw.decode("utf-8"))
            signed_url = payload.get("url") if isinstance(payload, dict) else None
            if not isinstance(signed_url, str):
                raise StorageError("platform_storage_bad_response")
            parsed = urlsplit(signed_url)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                raise StorageError("platform_storage_bad_response")
            return signed_url
        except StorageError:
            raise
        except (HTTPError, URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError) as error:
            raise StorageError("platform_storage_signing_failed") from error

    @staticmethod
    def _https_target(signed_url: str) -> tuple[http.client.HTTPSConnection, str]:
        parsed = urlsplit(signed_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise StorageError("invalid_signed_storage_url")
        connection = http.client.HTTPSConnection(
            parsed.hostname,
            parsed.port or 443,
            timeout=120,
            context=ssl.create_default_context(),
        )
        target = parsed.path or "/"
        if parsed.query:
            target += "?" + parsed.query
        return connection, target

    def put_bytes(self, key: str, content: bytes, content_type: str) -> None:
        signed_url = self._presigned_url("put", key)
        connection, target = self._https_target(signed_url)
        try:
            connection.putrequest("PUT", target, skip_accept_encoding=True)
            connection.putheader("Content-Length", str(len(content)))
            connection.putheader("Content-Type", content_type)
            connection.endheaders(content)
            response = connection.getresponse()
            response.read(4096)
            if response.status < 200 or response.status >= 300:
                raise StorageError("platform_storage_upload_failed")
        except StorageError:
            raise
        except (OSError, http.client.HTTPException, TimeoutError) as error:
            raise StorageError("platform_storage_upload_failed") from error
        finally:
            connection.close()

    def put_file(self, key: str, source: Path, content_type: str, *, max_bytes: int) -> None:
        size = source.stat().st_size
        if size <= 0 or size > max_bytes:
            raise StorageError("media_size_out_of_range")
        signed_url = self._presigned_url("put", key)
        connection, target = self._https_target(signed_url)
        try:
            connection.putrequest("PUT", target, skip_accept_encoding=True)
            connection.putheader("Content-Length", str(size))
            connection.putheader("Content-Type", content_type)
            connection.endheaders()
            sent = 0
            with source.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    sent += len(chunk)
                    if sent > max_bytes:
                        raise StorageError("media_size_out_of_range")
                    connection.send(chunk)
            if sent != size:
                raise StorageError("media_upload_incomplete")
            response = connection.getresponse()
            response.read(4096)
            if response.status < 200 or response.status >= 300:
                raise StorageError("platform_storage_upload_failed")
        except StorageError:
            raise
        except (OSError, http.client.HTTPException, TimeoutError) as error:
            raise StorageError("platform_storage_upload_failed") from error
        finally:
            connection.close()

    def download_file(self, key: str, target: Path, *, max_bytes: int) -> int:
        signed_url = self._presigned_url("get", key)
        request = Request(signed_url, headers={"Accept": "application/octet-stream"}, method="GET")
        target.parent.mkdir(parents=True, exist_ok=True)
        total = 0
        try:
            with urlopen(request, timeout=120) as response, target.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        raise StorageError("media_size_out_of_range")
                    output.write(chunk)
            if total <= 0:
                raise StorageError("platform_storage_empty_object")
            os.chmod(target, 0o600)
            return total
        except StorageError:
            target.unlink(missing_ok=True)
            raise
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            target.unlink(missing_ok=True)
            raise StorageError("platform_storage_download_failed") from error
