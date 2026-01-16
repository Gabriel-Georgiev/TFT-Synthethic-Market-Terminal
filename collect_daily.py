import os
import json
from config import CHALLENGER_PLAYER_LIMIT, MATCHES_PER_PLAYER, TOP_N_TRAITS, RAW_DAILY_PATH
from config import MIN_GAMES_PER_COMP
from api.tft_league import get_challenger_entries
from api.tft_match import get_match_ids_by_puuid, get_match
from engine.stats_engine import aggregate_comp_stats
from engine.pricing import price_from_w4p
from engine.market_store import upsert_day_book

def main():
    entries = get_challenger_entries()[:CHALLENGER_PLAYER_LIMIT]
    puuids = [e["puuid"] for e in entries]

    seen = set()
    matches = []

    for i, puuid in enumerate(puuids, start=1):
        print(f"[{i}/{len(puuids)}] fetching match ids...")
        ids = get_match_ids_by_puuid(puuid, count=MATCHES_PER_PLAYER)
        for mid in ids:
            if mid in seen:
                continue
            seen.add(mid)
            matches.append(get_match(mid))

    os.makedirs("data", exist_ok=True)

    with open(RAW_DAILY_PATH, "w", encoding="utf-8") as f:
        json.dump(matches, f)

    stats = aggregate_comp_stats(matches, top_n_traits=TOP_N_TRAITS)

    symbol_to_row = {}

    for sym, s in stats.items():
        games = s["games"]
        if games < MIN_GAMES_PER_COMP:
            continue

        close = price_from_w4p(s["win_rate"], s["top4_rate"], s["pick_rate"])
        symbol_to_row[sym] = {"close": close, "games": games}

    day = upsert_day_book(symbol_to_row)
    print(f"Saved closes for day {day}. Symbols (filtered): {len(symbol_to_row)}")

if __name__ == "__main__":
    main()