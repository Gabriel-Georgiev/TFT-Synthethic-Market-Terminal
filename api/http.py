import time
import requests
from config import API_KEY

class RiotApiError(Exception):
    pass

def riot_get(url: str, params=None, timeout=20, max_retries=6):
    if not API_KEY:
        raise RiotApiError("API_KEY is missing in config.py")

    headers = {"X-Riot-Token": API_KEY}

    for attempt in range(max_retries):
        r = requests.get(url, headers=headers, params=params, timeout=timeout)

        if r.status_code == 200:
            return r.json()

        if r.status_code == 429:
            retry_after = r.headers.get("Retry-After")
            sleep_s = int(retry_after) if retry_after and retry_after.isdigit() else (2 + attempt)
            time.sleep(sleep_s)
            continue

        try:
            body = r.json()
        except Exception:
            body = r.text

        raise RiotApiError(f"HTTP {r.status_code} for {url} params={params} body={body}")

    raise RiotApiError(f"Too many retries (429) for {url}")