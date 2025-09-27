import logging
from collections.abc import Iterator
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)


class GitHubAPIClient:
    """
    Pretty basic GitHub API client to fetch user events, supporting pagination and error handling.

    Usage:

    with GitHubAPIClient() as client:
        for event in client.get_user_events("matagus"):
            print(event)
    """

    BASE_URL = "https://api.github.com"
    DEFAULT_TIMEOUT = 30
    PER_PAGE = 100

    def __init__(self, session: requests.Session | None = None):
        """
        Creates a new GitHub API client. If no session is provided, a new one will be created.
        """

        self.session = session or requests.Session()
        self.session.headers.update({"Accept": "application/vnd.github.v3+json", "User-Agent": "gh-user-stats/1.0"})

    def __enter__(self):
        """
        Context manager for the GitHub API client, so we can use it in a "with" block.
        """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        This will be called when at the end when exiting the client in a "with" block.
        """
        self.session.close()

    def get_user_events(self, username: str) -> Iterator[dict]:
        """
        Fetches all user events with pagination and error handling.
        """

        url = urljoin(self.BASE_URL, f"/users/{username}/events?per_page={self.PER_PAGE}")

        while url:
            try:
                response = self.session.get(url, timeout=self.DEFAULT_TIMEOUT)
                response.raise_for_status()

                # Check rate limiting
                if int(response.headers.get("X-RateLimit-Remaining", 1)) == 0:
                    raise Exception("GitHub API rate limit exceeded")

                events = response.json()
                
                # Stop pagination if we get an empty response
                if not events:
                    break
                
                yield from events

                # Handle pagination of results to get all the events available
                url = response.links and response.links.get("next", {}).get("url") or None

            except requests.RequestException as e:
                logger.error(f"API request failed: {e}")
                raise
