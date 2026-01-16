import json
import os

WATCHLIST_PATH = os.path.join("data", "watchlist.json")


def load_watchlist() -> set[str]:
    if not os.path.exists(WATCHLIST_PATH):
        return set()
    try:
        with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return set(str(x) for x in data)
        return set()
    except Exception:
        return set()


def save_watchlist(items: set[str]) -> None:
    os.makedirs(os.path.dirname(WATCHLIST_PATH), exist_ok=True)
    with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(items), f, indent=2)


def toggle_watch(symbol: str) -> bool:
    wl = load_watchlist()
    if symbol in wl:
        wl.remove(symbol)
        save_watchlist(wl)
        return False
    wl.add(symbol)
    save_watchlist(wl)
    return True
