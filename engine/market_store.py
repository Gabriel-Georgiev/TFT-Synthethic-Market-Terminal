import json
import os
import datetime
from typing import Any
from config import MARKET_HISTORY_PATH


def load_history() -> dict:
    if not os.path.exists(MARKET_HISTORY_PATH):
        return {}

    with open(MARKET_HISTORY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_day_book(book: dict[str, Any]) -> dict[str, dict]:
    out = {}
    for sym, val in book.items():
        if isinstance(val, dict):
            close = float(val.get("close", 0.0))
            games = val.get("games", None)
            out[sym] = {"close": close, "games": int(games) if games is not None else None}
        else:
            out[sym] = {"close": float(val), "games": None}
    return out


def list_days(history: dict) -> list[str]:
    return sorted(history.keys())


def latest_day(history: dict) -> str | None:
    days = list_days(history)
    return days[-1] if days else None


def _parse_variant_symbol(sym: str) -> tuple[str, str] | None:
    if not sym.startswith("/") or ":XCOMP" not in sym:
        return None

    core = sym[1:].split(":XCOMP")[0]  # "BILGEWATER4"
    if not core:
        return None

    i = len(core) - 1
    while i >= 0 and core[i].isdigit():
        i -= 1

    trait = core[: i + 1]  # "BILGEWATER"
    digits = core[i + 1 :]  # "4"
    if not trait or not digits:
        return None  # not a variant

    base = f"/{trait}:XCOMP"
    return base, trait


def compute_base_trait_book_for_day(day_book: dict[str, dict]) -> dict[str, dict]:
    buckets: dict[str, list[tuple[float, int | None]]] = {}

    for sym, row in day_book.items():
        parsed = _parse_variant_symbol(sym)
        if not parsed:
            continue
        base_sym, _trait = parsed
        buckets.setdefault(base_sym, []).append((row["close"], row["games"]))

    base_book: dict[str, dict] = {}
    for base_sym, items in buckets.items():
        closes = [c for c, _g in items]
        games_list = [g for _c, g in items if g is not None]

        if games_list and len(games_list) == len(items):
            total_games = sum(games_list)
            if total_games > 0:
                weighted = sum(close * g for (close, g) in items) / total_games
            else:
                weighted = sum(closes) / len(closes)
            base_book[base_sym] = {"close": float(weighted), "games": int(total_games)}
        else:
            base_book[base_sym] = {"close": float(sum(closes) / len(closes)), "games": None}

    return base_book


def get_latest_base_traits_sorted(min_games: int = 1) -> list[tuple[str, float, int | None]]:
    history = load_history()
    day = latest_day(history)
    if not day:
        return []

    day_book = _normalize_day_book(history[day])
    base_book = compute_base_trait_book_for_day(day_book)

    rows = []
    for sym, row in base_book.items():
        games = row["games"]
        if games is not None and games < min_games:
            continue
        rows.append((sym, row["close"], games))

    rows.sort(key=lambda x: x[1], reverse=True)
    return rows


def get_variants_for_base_on_latest_day(base_symbol: str, min_games: int = 1) -> list[tuple[str, float, int | None]]:
    history = load_history()
    day = latest_day(history)
    if not day:
        return []

    day_book = _normalize_day_book(history[day])
    trait = base_symbol.replace("/", "").replace(":XCOMP", "")

    rows = []
    for sym, row in day_book.items():
        parsed = _parse_variant_symbol(sym)
        if not parsed:
            continue
        base_sym, t = parsed
        if base_sym != base_symbol or t != trait:
            continue

        games = row["games"]
        if games is not None and games < min_games:
            continue
        rows.append((sym, row["close"], games))

    rows.sort(key=lambda x: x[1], reverse=True)
    return rows


def series_for_symbol(symbol: str) -> list[tuple[str, float, int | None]]:
    history = load_history()
    days = list_days(history)
    if not days:
        return []

    points = []

    is_base = symbol.startswith("/") and symbol.endswith(":XCOMP") and _parse_variant_symbol(symbol) is None

    for day in days:
        day_book = _normalize_day_book(history[day])

        if is_base:
            base_book = compute_base_trait_book_for_day(day_book)
            if symbol in base_book:
                row = base_book[symbol]
                points.append((day, float(row["close"]), row["games"]))
        else:
            if symbol in day_book:
                row = day_book[symbol]
                points.append((day, float(row["close"]), row["games"]))

    return points

def upsert_day_book(symbol_to_row: dict, day: str | None = None) -> str:
    if day is None:
        day = datetime.date.today().isoformat()

    history = load_history()
    history.setdefault(day, {})
    history[day].update(symbol_to_row)

    os.makedirs(os.path.dirname(MARKET_HISTORY_PATH) or ".", exist_ok=True)
    with open(MARKET_HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

    return day