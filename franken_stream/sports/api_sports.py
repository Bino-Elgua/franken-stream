"""Sports provider — live scores via API-Sports (free tier: 100 req/day)."""

from typing import Dict, List, Optional

import requests


class SportsProvider:
    """
    Fetch live football/soccer match data from api-sports.io.

    An API key is optional: without one the provider returns an empty list
    rather than raising an error, so the rest of the application still works.

    Free tier: 100 requests / day — sufficient for casual use.
    """

    API_URL = "https://v3.football.api-sports.io"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self._headers = {"x-apisports-key": api_key} if api_key else {}

    @property
    def available(self) -> bool:
        """True when an API key has been configured."""
        return bool(self.api_key)

    def get_live_matches(self) -> List[Dict]:
        """Return all currently live matches (requires API key)."""
        if not self.available:
            return []
        return self._fetch_fixtures({"live": "all"})

    def get_fixtures_today(self) -> List[Dict]:
        """Return today's scheduled fixtures (requires API key)."""
        if not self.available:
            return []
        from datetime import date
        return self._fetch_fixtures({"date": date.today().isoformat()})

    def search_fixtures(self, team: str) -> List[Dict]:
        """Search for fixtures by team name (requires API key)."""
        if not self.available:
            return []
        # First look up the team ID
        try:
            resp = requests.get(
                f"{self.API_URL}/teams",
                params={"search": team},
                headers=self._headers,
                timeout=10,
            )
            resp.raise_for_status()
            teams = resp.json().get("response", [])
            if not teams:
                return []
            team_id = teams[0]["team"]["id"]
            return self._fetch_fixtures({"team": team_id, "next": 5})
        except Exception:
            return []

    def _fetch_fixtures(self, params: Dict) -> List[Dict]:
        try:
            resp = requests.get(
                f"{self.API_URL}/fixtures",
                params=params,
                headers=self._headers,
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return []

        results = []
        for match in data.get("response", []):
            fixture = match.get("fixture", {})
            teams = match.get("teams", {})
            goals = match.get("goals", {})
            league = match.get("league", {})
            status = fixture.get("status", {})

            home_score = goals.get("home")
            away_score = goals.get("away")
            score = (
                f"{home_score}-{away_score}"
                if home_score is not None and away_score is not None
                else "vs"
            )

            results.append({
                "home": teams.get("home", {}).get("name", "Unknown"),
                "away": teams.get("away", {}).get("name", "Unknown"),
                "score": score,
                "league": league.get("name", "Unknown"),
                "country": league.get("country", ""),
                "elapsed": status.get("elapsed"),
                "status": status.get("short", ""),
                "date": fixture.get("date", ""),
                "type": "live_sport",
                "source": "api-sports",
            })

        return results
