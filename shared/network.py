"""HTTP client helpers for service-to-service calls."""
import httpx
from fastapi import HTTPException
from .config import INTERNAL_KEY, service_url

def fetch(name: str, method: str, path: str, *, payload=None, internal=False):
    headers = {'X-Internal-Key': INTERNAL_KEY} if internal else {}
    try:
        with httpx.Client(timeout=4) as client:
            r = client.request(method, service_url(name) + path, json=payload, headers=headers)
        if r.status_code >= 400:
            detail = r.json().get('detail', r.text)
            raise HTTPException(r.status_code, f'{name}: {detail}')
        return r.json()
    except (httpx.ConnectError, httpx.TimeoutException):
        raise HTTPException(503, f'{name} service is unavailable')
