import argparse
import dataclasses
import json
import logging
from collections import Counter, defaultdict
from collections.abc import Iterator

from github_client import GitHubAPIClient


logger = logging.getLogger(__name__)


def map_event_to_activity(event: dict) -> str | None:
    """
    Maps a GitHub Event to our custom activity types. Returns None if the event doesn't fit any custom activity.
    """

    EVENT_TYPE_MAPPING = {
        "PushEvent": "commits",
        "PullRequestEvent": "pull requests",
        "PullRequestReviewEvent": "pull requests",
        "IssueCommentEvent": "comments",
        "PullRequestReviewCommentEvent": "comments",
        "CommitCommentEvent": "comments",
    }

    event_type = event.get("type")

    # Special handling for PullRequestEvent to detect merges
    if event_type == "PullRequestEvent":
        payload = event.get("payload", {})
        action = payload.get("action")
        pull_request = payload.get("pull_request", {})

        # Check if this is a merge event
        if action == "closed" and pull_request.get("merged"):
            return "merges"
        else:
            return "pull requests"

    # Map other event types using the mapping dictionary
    return EVENT_TYPE_MAPPING.get(event_type)


@dataclasses.dataclass
class RepoTopActivities:
    """
    Represents the top activities for a repo, owned or not by a user.
    """

    name: str
    top_activities: list[str]
    owned: bool

    def __repr__(self) -> str:
        return json.dumps(self.__dict__)


def get_top_activities_by_repo_for(username: str) -> Iterator[RepoTopActivities]:
    """
    Returns an iterator of RepoTopActivities for a given Github username
    """

    events_by_repo = defaultdict(Counter)

    with GitHubAPIClient() as client:
        for event in client.get_user_events(username):
            # Skip events that don't have required fields
            if not isinstance(event, dict) or "repo" not in event:
                logger.warning("Skipping event: missing 'repo' field")
                continue

            repo_data = event.get("repo")
            if not isinstance(repo_data, dict) or "name" not in repo_data:
                logger.warning("Skipping event: missing 'repo.name' field")
                continue

            # Map the event type to our custom activity
            activity = map_event_to_activity(event)

            # Only process events that map to our custom activities
            if activity:
                events_by_repo[repo_data["name"]].update([activity])

    for repo_full_name, events_counter in events_by_repo.items():
        top3_activities = [event[0] for event in events_counter.most_common(3)]
        owned = repo_full_name.split("/")[0] == username
        yield RepoTopActivities(repo_full_name, top3_activities, owned)


if __name__ == "__main__":
    """
    Example usage:
        python gh_user_stats.py <username>
    """

    parser = argparse.ArgumentParser(prog="gh_user_stats")
    parser.add_argument("username")
    args = parser.parse_args()
    username = args.username

    # Always output JSON for consistency, even if empty
    activities = list(get_top_activities_by_repo_for(username))
    print(activities)
