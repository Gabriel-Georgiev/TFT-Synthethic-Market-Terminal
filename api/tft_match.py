from config import REGION
from api.http import riot_get

def get_match_ids_by_puuid(puuid: str, count: int):
    url = f"https://{REGION}.api.riotgames.com/tft/match/v1/matches/by-puuid/{puuid}/ids"
    return riot_get(url, params={"count": count})

def get_match(match_id: str):
    url = f"https://{REGION}.api.riotgames.com/tft/match/v1/matches/{match_id}"
    return riot_get(url)