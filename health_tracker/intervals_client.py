import requests
from .config import INTERVALS_API_KEY, INTERVALS_ATHLETE_ID

class IntervalsClient:
    def __init__(self):
        self.auth = ('API_KEY', INTERVALS_API_KEY)
        self.base_url = f"https://intervals.icu/api/v1/athlete/{INTERVALS_ATHLETE_ID}"

    def get(self, endpoint, params=None):
        url = f"{self.base_url}/{endpoint}"
        response = requests.get(url, auth=self.auth, params=params)
        response.raise_for_status()
        return response.json()

    def post(self, endpoint, payload):
        url = f"{self.base_url}/{endpoint}"
        # Some endpoints use athlete/0/ for post, but Intervals API usually accepts the ID too.
        # Standardizing to athlete/{ID} unless it fails.
        response = requests.post(url, auth=self.auth, json=payload)
        response.raise_for_status()
        return response.json()

    def get_wellness(self, oldest, newest):
        return self.get("wellness", {"oldest": oldest, "newest": newest})

    def get_events(self, oldest, newest):
        return self.get("events", {"oldest": oldest, "newest": newest})

    def get_activities(self, oldest, newest):
        return self.get("activities", {"oldest": oldest, "newest": newest})

    def create_event(self, payload):
        # The API documentation often uses athlete/0/events for the current user
        url = f"https://intervals.icu/api/v1/athlete/0/events"
        response = requests.post(url, auth=self.auth, json=payload)
        response.raise_for_status()
        return response.json()
