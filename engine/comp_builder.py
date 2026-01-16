def _clean_trait(raw: str) -> str:
    if "_" in raw:
        raw = raw.split("_", 1)[1]
    return raw.upper()

def comp_symbol_from_participant(participant: dict, top_n_traits: int = 1) -> str:
    traits = participant.get("traits", [])
    active = []
    for t in traits:
        n = t.get("num_units", 0)
        if n > 0:
            active.append((_clean_trait(t.get("name", "UNKNOWN")), n))

    active.sort(key=lambda x: x[1], reverse=True)
    top = active[:top_n_traits]
    if not top:
        return "/UNKNOWN:XCOMP"

    signature = "-".join([f"{name}{num}" for name, num in top])
    return f"/{signature}:XCOMP"