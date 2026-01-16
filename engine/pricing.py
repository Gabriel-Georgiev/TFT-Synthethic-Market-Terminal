def price_from_w4p(win_rate: float, top4_rate: float, pick_rate: float) -> float:
    return (win_rate * 50) + (top4_rate * 30) + (pick_rate * 20)
