from config import PLATFORM
from api.http import riot_get

def get_challenger_entries():
    url = f"https://{PLATFORM}.api.riotgames.com/tft/league/v1/challenger"
    data = riot_get(url)
    return data.get("entries", [])