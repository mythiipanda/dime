import requests
import json

url = "https://stats.nba.com/stats/synergyplaytypes"

headers = {
    "accept": "*/*",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "en-US,en;q=0.9",
    "connection": "keep-alive",
    "host": "stats.nba.com",
    "origin": "https://www.nba.com",
    "referer": "https://www.nba.com/",
    "sec-ch-ua": '"Chromium";v="136", "Brave";v="136", "Not.A/Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "sec-gpc": "1",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
}

params = {
    "LeagueID": "00",
    "PerMode": "PerGame",
    "PlayType": "Postup",
    "PlayerOrTeam": "P",
    "SeasonType": "Regular Season",
    "SeasonYear": "2024-25",
    "TypeGrouping": "offensive"
}

try:
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()  # Raise an exception for HTTP errors

    data = response.json()
    print(json.dumps(data, indent=4))

except requests.exceptions.RequestException as e:
    print(f"An error occurred: {e}")
    if response is not None:
        print(f"Response status code: {response.status_code}")
        print(f"Response text: {response.text}")
except json.JSONDecodeError:
    print("Failed to decode JSON response.")
    print(f"Response text: {response.text}")