"""
Refactored tests for development_trends.py module with proper mocking strategy
"""

import json
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

import pytest
import requests

from development_trends import (
    get_top_activities_by_repo_for,
    RepoTopActivities,
    map_event_to_activity,
)


# ============================================================================
# Test Data Builders
# ============================================================================

class EventBuilder:
    """Helper class to build GitHub event test data"""

    @staticmethod
    def push_event(repo_name: str = "user/repo") -> Dict[str, Any]:
        """Create a PushEvent"""
        return {
            "type": "PushEvent",
            "repo": {"name": repo_name},
            "payload": {}
        }

    @staticmethod
    def pull_request_event(
        repo_name: str = "user/repo",
        action: str = "opened",
        merged: bool = False
    ) -> Dict[str, Any]:
        """Create a PullRequestEvent"""
        return {
            "type": "PullRequestEvent",
            "repo": {"name": repo_name},
            "payload": {
                "action": action,
                "pull_request": {"merged": merged}
            }
        }

    @staticmethod
    def merge_event(repo_name: str = "user/repo") -> Dict[str, Any]:
        """Create a merge event (closed PR with merged=true)"""
        return EventBuilder.pull_request_event(repo_name, "closed", True)

    @staticmethod
    def issue_comment_event(repo_name: str = "user/repo") -> Dict[str, Any]:
        """Create an IssueCommentEvent"""
        return {
            "type": "IssueCommentEvent",
            "repo": {"name": repo_name},
            "payload": {}
        }

    @staticmethod
    def pull_request_review_event(repo_name: str = "user/repo") -> Dict[str, Any]:
        """Create a PullRequestReviewEvent"""
        return {
            "type": "PullRequestReviewEvent",
            "repo": {"name": repo_name},
            "payload": {}
        }

    @staticmethod
    def pull_request_review_comment_event(repo_name: str = "user/repo") -> Dict[str, Any]:
        """Create a PullRequestReviewCommentEvent"""
        return {
            "type": "PullRequestReviewCommentEvent",
            "repo": {"name": repo_name},
            "payload": {}
        }

    @staticmethod
    def commit_comment_event(repo_name: str = "user/repo") -> Dict[str, Any]:
        """Create a CommitCommentEvent"""
        return {
            "type": "CommitCommentEvent",
            "repo": {"name": repo_name},
            "payload": {}
        }

    @staticmethod
    def unmapped_event(repo_name: str = "user/repo", event_type: str = "WatchEvent") -> Dict[str, Any]:
        """Create an event that doesn't map to any activity"""
        return {
            "type": event_type,
            "repo": {"name": repo_name},
            "payload": {}
        }


class ResponseBuilder:
    """Helper class to build mock HTTP responses"""

    @staticmethod
    def success_response(
        data: List[Dict[str, Any]],
        next_url: str = None,
        rate_limit_remaining: str = "5000"
    ) -> Mock:
        """Build a successful API response"""
        response = Mock()
        response.status_code = 200
        response.json.return_value = data
        response.headers = {"X-RateLimit-Remaining": rate_limit_remaining}

        if next_url:
            response.links = {"next": {"url": next_url}}
        else:
            response.links = None

        return response

    @staticmethod
    def error_response(status_code: int, error_message: str) -> Mock:
        """Build an error API response"""
        response = Mock()
        response.status_code = status_code
        response.raise_for_status.side_effect = requests.HTTPError(error_message)
        return response


# ============================================================================
# Unit Tests
# ============================================================================

class TestMapEventToActivity:
    """Test suite for map_event_to_activity function"""

    def test_push_event_maps_to_commits(self):
        """Test that PushEvent maps to 'commits'"""
        event = EventBuilder.push_event()
        assert map_event_to_activity(event) == "commits"

    def test_pull_request_event_open_maps_to_pull_requests(self):
        """Test that PullRequestEvent (non-merge) maps to 'pull requests'"""
        event = EventBuilder.pull_request_event(action="opened")
        assert map_event_to_activity(event) == "pull requests"

    def test_pull_request_event_merged_maps_to_merges(self):
        """Test that PullRequestEvent (merged) maps to 'merges'"""
        event = EventBuilder.merge_event()
        assert map_event_to_activity(event) == "merges"

    def test_pull_request_review_event_maps_to_pull_requests(self):
        """Test that PullRequestReviewEvent maps to 'pull requests'"""
        event = EventBuilder.pull_request_review_event()
        assert map_event_to_activity(event) == "pull requests"

    def test_comment_events_map_to_comments(self):
        """Test that various comment events map to 'comments'"""
        comment_events = [
            EventBuilder.issue_comment_event(),
            EventBuilder.pull_request_review_comment_event(),
            EventBuilder.commit_comment_event(),
        ]
        for event in comment_events:
            assert map_event_to_activity(event) == "comments"

    def test_unmapped_event_returns_none(self):
        """Test that unmapped events return None"""
        event = EventBuilder.unmapped_event()
        assert map_event_to_activity(event) is None


class TestGetTopActivitiesByRepoFor:
    """Test suite for get_top_activities_by_repo_for function with proper session mocking"""

    @patch("github_client.requests.Session")
    def test_happy_case_less_than_100_events_no_pagination(self, mock_session_class):
        """Test successful retrieval with less than 100 events (no pagination)"""

        # Setup mock session
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # Create test events
        mock_events = [
            # Events for user's own repo
            EventBuilder.push_event("testuser/my-repo"),
            EventBuilder.push_event("testuser/my-repo"),
            EventBuilder.pull_request_event("testuser/my-repo"),
            EventBuilder.issue_comment_event("testuser/my-repo"),
            EventBuilder.push_event("testuser/my-repo"),
            EventBuilder.merge_event("testuser/my-repo"),
            EventBuilder.commit_comment_event("testuser/my-repo"),
            # Events for another user's repo
            EventBuilder.pull_request_review_event("otheruser/other-repo"),
            EventBuilder.pull_request_review_comment_event("otheruser/other-repo"),
            EventBuilder.pull_request_review_event("otheruser/other-repo"),
            EventBuilder.issue_comment_event("otheruser/other-repo"),
            # Events that should be ignored
            EventBuilder.unmapped_event("someorg/some-repo", "WatchEvent"),
            EventBuilder.unmapped_event("someorg/some-repo", "ForkEvent"),
        ]

        # Setup mock response
        mock_response = ResponseBuilder.success_response(mock_events)
        mock_session.get.return_value = mock_response

        # Call the function
        results = list(get_top_activities_by_repo_for("testuser"))

        # Verify HTTP call was made correctly
        mock_session.get.assert_called_once_with(
            "https://api.github.com/users/testuser/events?per_page=100",
            timeout=30
        )

        # Verify session lifecycle
        mock_session.headers.update.assert_called_once_with({
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "gh-user-stats/1.0"
        })
        mock_session.close.assert_called_once()

        # Assert the results
        assert len(results) == 2

        # Find each repo in results
        my_repo = next(r for r in results if r.name == "testuser/my-repo")
        other_repo = next(r for r in results if r.name == "otheruser/other-repo")

        # Check my-repo stats
        assert my_repo.owned is True
        assert "commits" in my_repo.top_activities  # 3 occurrences
        assert "comments" in my_repo.top_activities  # 2 occurrences
        assert len(my_repo.top_activities) <= 3

        # Check other-repo stats
        assert other_repo.owned is False
        assert set(other_repo.top_activities) <= {"pull requests", "comments"}

    @patch("github_client.requests.Session")
    def test_pagination_handling(self, mock_session_class):
        """Test proper handling of paginated responses with Link headers"""

        # Setup mock session
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # Create events for multiple pages
        first_page_events = [EventBuilder.push_event("testuser/repo") for _ in range(100)]
        second_page_events = [EventBuilder.pull_request_event("testuser/repo") for _ in range(50)]
        third_page_events = [EventBuilder.issue_comment_event("testuser/repo") for _ in range(25)]

        # Setup paginated responses
        first_response = ResponseBuilder.success_response(
            first_page_events,
            next_url="https://api.github.com/users/testuser/events?page=2&per_page=100"
        )
        second_response = ResponseBuilder.success_response(
            second_page_events,
            next_url="https://api.github.com/users/testuser/events?page=3&per_page=100"
        )
        third_response = ResponseBuilder.success_response(third_page_events)

        # Configure mock to return different responses for each call
        mock_session.get.side_effect = [first_response, second_response, third_response]

        # Call the function
        results = list(get_top_activities_by_repo_for("testuser"))

        # Verify all three API calls were made
        assert mock_session.get.call_count == 3

        # Verify the URLs called
        calls = mock_session.get.call_args_list
        assert calls[0][0][0] == "https://api.github.com/users/testuser/events?per_page=100"
        assert calls[1][0][0] == "https://api.github.com/users/testuser/events?page=2&per_page=100"
        assert calls[2][0][0] == "https://api.github.com/users/testuser/events?page=3&per_page=100"

        # Verify results
        assert len(results) == 1
        repo = results[0]
        assert repo.name == "testuser/repo"
        assert repo.owned is True
        # Should have: 100 commits, 50 pull requests, 25 comments
        assert repo.top_activities == ["commits", "pull requests", "comments"]

    @patch("github_client.requests.Session")
    def test_rate_limit_detected(self, mock_session_class):
        """Test detection of GitHub API rate limiting"""

        # Setup mock session
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # Setup response with rate limit exhausted
        mock_response = ResponseBuilder.success_response([], rate_limit_remaining="0")
        mock_session.get.return_value = mock_response

        # Should raise exception for rate limit
        with pytest.raises(Exception, match="GitHub API rate limit exceeded"):
            list(get_top_activities_by_repo_for("testuser"))

        # Verify session was properly closed even on error
        mock_session.close.assert_called_once()

    @patch("github_client.requests.Session")
    def test_network_failure(self, mock_session_class):
        """Test handling of network failures"""

        # Setup mock session
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # Setup session to raise network error
        mock_session.get.side_effect = requests.RequestException("Network error: connection timeout")

        # Should propagate the network exception
        with pytest.raises(requests.RequestException, match="Network error"):
            list(get_top_activities_by_repo_for("testuser"))

        # Verify session was closed
        mock_session.close.assert_called_once()

    @patch("github_client.requests.Session")
    def test_http_error_500(self, mock_session_class):
        """Test handling of server errors (5xx status codes)"""

        # Setup mock session
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # Setup response that raises HTTP error
        mock_response = ResponseBuilder.error_response(500, "500 Internal Server Error")
        mock_session.get.return_value = mock_response

        # Should propagate the HTTP error
        with pytest.raises(requests.HTTPError, match="500 Internal Server Error"):
            list(get_top_activities_by_repo_for("testuser"))

        # Verify session was closed
        mock_session.close.assert_called_once()

    @patch("github_client.requests.Session")
    def test_http_error_404(self, mock_session_class):
        """Test handling of 404 Not Found errors"""

        # Setup mock session
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # Setup 404 response
        mock_response = ResponseBuilder.error_response(404, "404 Not Found: User does not exist")
        mock_session.get.return_value = mock_response

        # Should propagate the HTTP error
        with pytest.raises(requests.HTTPError, match="404 Not Found"):
            list(get_top_activities_by_repo_for("testuser"))

    @patch("github_client.requests.Session")
    def test_timeout_handling(self, mock_session_class):
        """Test handling of request timeouts"""

        # Setup mock session
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # Setup session to raise timeout error
        mock_session.get.side_effect = requests.Timeout("Request timed out after 30 seconds")

        # Should propagate the timeout exception
        with pytest.raises(requests.Timeout, match="Request timed out"):
            list(get_top_activities_by_repo_for("testuser"))

        # Verify session was closed
        mock_session.close.assert_called_once()

    @patch("github_client.requests.Session")
    def test_malformed_json_response(self, mock_session_class):
        """Test handling of malformed JSON responses"""

        # Setup mock session
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # Setup response with invalid JSON
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"X-RateLimit-Remaining": "5000"}
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_response.links = None
        mock_session.get.return_value = mock_response

        # Should propagate the JSON error
        with pytest.raises(json.JSONDecodeError):
            list(get_top_activities_by_repo_for("testuser"))

    @patch("github_client.requests.Session")
    def test_user_with_no_activity(self, mock_session_class):
        """Test handling of user with no activity"""

        # Setup mock session
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # Setup response with empty list
        mock_response = ResponseBuilder.success_response([])
        mock_session.get.return_value = mock_response

        # Call the function
        results = list(get_top_activities_by_repo_for("testuser"))

        # Should return empty list for user with no activity
        assert results == []

        # Verify the API was still called
        mock_session.get.assert_called_once_with(
            "https://api.github.com/users/testuser/events?per_page=100",
            timeout=30
        )

    @patch("github_client.requests.Session")
    def test_mixed_event_types_and_multiple_repos(self, mock_session_class):
        """Test complex scenario with multiple repos and varied event types"""

        # Setup mock session
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # Create complex event mix
        events = []

        # Repo 1: Heavy commit activity
        for _ in range(60):
            events.append(EventBuilder.push_event("testuser/active-repo"))
        for _ in range(20):
            events.append(EventBuilder.pull_request_event("testuser/active-repo"))
        for _ in range(10):
            events.append(EventBuilder.issue_comment_event("testuser/active-repo"))

        # Repo 2: Mostly PR reviews
        for _ in range(30):
            events.append(EventBuilder.pull_request_review_event("otheruser/review-repo"))
        for _ in range(25):
            events.append(EventBuilder.pull_request_review_comment_event("otheruser/review-repo"))

        # Repo 3: Mixed activity
        for _ in range(5):
            events.append(EventBuilder.push_event("testuser/mixed-repo"))
        for _ in range(5):
            events.append(EventBuilder.merge_event("testuser/mixed-repo"))
        for _ in range(3):
            events.append(EventBuilder.issue_comment_event("testuser/mixed-repo"))

        # Add some unmapped events that should be ignored
        for _ in range(10):
            events.append(EventBuilder.unmapped_event("random/repo", "StarEvent"))

        # Setup response
        mock_response = ResponseBuilder.success_response(events)
        mock_session.get.return_value = mock_response

        # Call the function
        results = list(get_top_activities_by_repo_for("testuser"))

        # Should have 3 repos (unmapped events ignored)
        assert len(results) == 3

        # Verify each repo's top activities
        active_repo = next(r for r in results if r.name == "testuser/active-repo")
        assert active_repo.owned is True
        assert active_repo.top_activities[0] == "commits"  # 60 occurrences
        assert active_repo.top_activities[1] == "pull requests"  # 20 occurrences
        assert active_repo.top_activities[2] == "comments"  # 10 occurrences

        review_repo = next(r for r in results if r.name == "otheruser/review-repo")
        assert review_repo.owned is False
        # Both "pull requests" and "comments" have high counts
        assert set(review_repo.top_activities) <= {"pull requests", "comments"}

        mixed_repo = next(r for r in results if r.name == "testuser/mixed-repo")
        assert mixed_repo.owned is True
        assert len(mixed_repo.top_activities) <= 3


class TestRepoTopActivities:
    """Test suite for RepoTopActivities dataclass"""

    def test_repr_returns_valid_json(self):
        """Test that __repr__ returns valid JSON representation"""

        repo = RepoTopActivities(
            name="testuser/test-repo",
            top_activities=["commits", "pull requests"],
            owned=True
        )

        # __repr__ should return valid JSON
        json_str = repr(repo)
        parsed = json.loads(json_str)

        assert parsed["name"] == "testuser/test-repo"
        assert parsed["top_activities"] == ["commits", "pull requests"]
        assert parsed["owned"] is True

    def test_dataclass_fields(self):
        """Test that dataclass correctly stores all fields"""

        repo = RepoTopActivities(
            name="otheruser/other-repo",
            top_activities=["merges", "comments", "commits"],
            owned=False
        )

        assert repo.name == "otheruser/other-repo"
        assert repo.top_activities == ["merges", "comments", "commits"]
        assert repo.owned is False

    def test_empty_top_activities(self):
        """Test dataclass with empty top activities list"""

        repo = RepoTopActivities(
            name="user/empty-repo",
            top_activities=[],
            owned=True
        )

        assert repo.top_activities == []
        # Should still serialize to valid JSON
        json_str = repr(repo)
        parsed = json.loads(json_str)
        assert parsed["top_activities"] == []


class TestGitHubAPIClient:
    """Test suite specifically for GitHubAPIClient behavior"""

    @patch("github_client.requests.Session")
    def test_session_headers_are_set_correctly(self, mock_session_class):
        """Test that the client sets correct headers on the session"""
        from github_client import GitHubAPIClient

        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        with GitHubAPIClient():
            pass

        # Verify headers were set
        mock_session.headers.update.assert_called_once_with({
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "gh-user-stats/1.0"
        })

        # Verify session was closed
        mock_session.close.assert_called_once()

    @patch("github_client.requests.Session")
    def test_custom_session_is_used(self, mock_session_class):
        """Test that a custom session can be provided and is used"""
        from github_client import GitHubAPIClient

        # Create a custom session
        custom_session = MagicMock()
        mock_response = ResponseBuilder.success_response([])
        custom_session.get.return_value = mock_response

        # Use the client with custom session
        with GitHubAPIClient(session=custom_session) as client:
            list(client.get_user_events("testuser"))

        # Verify our custom session was used, not a new one
        mock_session_class.assert_not_called()
        custom_session.get.assert_called_once()
        custom_session.close.assert_called_once()

    @patch("github_client.requests.Session")
    def test_raise_for_status_is_called(self, mock_session_class):
        """Test that raise_for_status is called on responses"""
        from github_client import GitHubAPIClient

        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # Create a response that will be checked
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()  # We'll verify this gets called
        mock_response.headers = {"X-RateLimit-Remaining": "5000"}
        mock_response.json.return_value = []
        mock_response.links = None
        mock_session.get.return_value = mock_response

        with GitHubAPIClient() as client:
            list(client.get_user_events("testuser"))

        # Verify raise_for_status was called
        mock_response.raise_for_status.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
