from collections import defaultdict
from engine.comp_builder import comp_symbol_from_participant

def aggregate_comp_stats(matches: list[dict], top_n_traits: int):
    stats = defaultdict(lambda: {"games": 0, "wins": 0, "top4": 0})
    total_boards = 0

    for match in matches:
        for p in match["info"]["participants"]:
            total_boards += 1
            sym = comp_symbol_from_participant(p, top_n_traits=top_n_traits)
            stats[sym]["games"] += 1

            placement = p.get("placement", 8)
            if placement == 1:
                stats[sym]["wins"] += 1
            if placement <= 4:
                stats[sym]["top4"] += 1

    for sym, s in stats.items():
        s["win_rate"] = s["wins"] / s["games"]
        s["top4_rate"] = s["top4"] / s["games"]
        s["pick_rate"] = s["games"] / total_boards if total_boards else 0.0

    return dict(stats)