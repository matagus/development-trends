"""
Integration tests for development_trends module using responses library
These tests provide a middle ground between unit tests and actual API calls
"""

from typing import Dict

import pytest
import responses
import requests

from development_trends import get_top_activities_by_repo_for
from test_development_trends import EventBuilder  # Reuse our test data builders


class IntegrationTestBase:
    """Base class with common integration test utilities"""

    BASE_URL = "https://api.github.com"

    @staticmethod
    def build_events_url(username: str, page: int = None) -> str:
        """Build the GitHub API URL for user events"""
        url = f"{IntegrationTestBase.BASE_URL}/users/{username}/events?per_page=100"
        if page:
            url += f"&page={page}"
        return url

    @staticmethod
    def build_link_header(username: str, current_page: int, has_next: bool) -> Dict[str, str]:
        """Build GitHub-style Link header for pagination"""
        if not has_next:
            return {}

        next_page = current_page + 1
        next_url = IntegrationTestBase.build_events_url(username, next_page)

        # GitHub's Link header format
        link_value = f'<{next_url}>; rel="next"'
        if current_page > 1:
            prev_url = IntegrationTestBase.build_events_url(username, current_page - 1)
            link_value = f'<{prev_url}>; rel="prev", {link_value}'

        return {"Link": link_value}


class TestIntegrationWithResponses(IntegrationTestBase):
    """Integration tests using the responses library"""

    @responses.activate
    def test_single_page_response(self):
        """Test handling of a single page of events"""

        # Create test events
        events = [
            EventBuilder.push_event("testuser/repo1"),
            EventBuilder.push_event("testuser/repo1"),
            EventBuilder.pull_request_event("testuser/repo1"),
            EventBuilder.issue_comment_event("testuser/repo2"),
            EventBuilder.merge_event("testuser/repo2"),
        ]

        # Mock the API response
        responses.add(
            responses.GET,
            self.build_events_url("testuser"),
            json=events,
            status=200,
            headers={
                "X-RateLimit-Remaining": "5000",
                "X-RateLimit-Limit": "5000",
            }
        )

        # Call our function
        results = list(get_top_activities_by_repo_for("testuser"))

        # Verify results
        assert len(results) == 2

        repo1 = next(r for r in results if r.name == "testuser/repo1")
        assert repo1.owned is True
        assert "commits" in repo1.top_activities

        repo2 = next(r for r in results if r.name == "testuser/repo2")
        assert repo2.owned is True

        # Verify the API was called correctly
        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == self.build_events_url("testuser")

    @responses.activate
    def test_paginated_response(self):
        """Test handling of paginated API responses"""

        # Create events for three pages
        page1_events = [EventBuilder.push_event(f"testuser/repo{i % 3}") for i in range(100)]
        page2_events = [EventBuilder.pull_request_event(f"testuser/repo{i % 3}") for i in range(100)]
        page3_events = [EventBuilder.issue_comment_event(f"testuser/repo{i % 3}") for i in range(50)]

        # Mock the first page with Link header
        responses.add(
            responses.GET,
            self.build_events_url("testuser"),
            json=page1_events,
            status=200,
            headers={
                **self.build_link_header("testuser", 1, has_next=True),
                "X-RateLimit-Remaining": "4997",
            }
        )

        # Mock the second page
        responses.add(
            responses.GET,
            self.build_events_url("testuser", 2),
            json=page2_events,
            status=200,
            headers={
                **self.build_link_header("testuser", 2, has_next=True),
                "X-RateLimit-Remaining": "4996",
            }
        )

        # Mock the third (final) page
        responses.add(
            responses.GET,
            self.build_events_url("testuser", 3),
            json=page3_events,
            status=200,
            headers={
                **self.build_link_header("testuser", 3, has_next=False),
                "X-RateLimit-Remaining": "4995",
            }
        )

        # Call our function
        results = list(get_top_activities_by_repo_for("testuser"))

        # Verify all three pages were requested
        assert len(responses.calls) == 3

        # Verify we got results for all repos
        assert len(results) == 3  # repo0, repo1, repo2

        for result in results:
            assert result.owned is True
            # Each repo should have all three activity types
            assert len(result.top_activities) == 3

    @responses.activate
    def test_rate_limit_response(self):
        """Test handling of rate limit exhaustion"""

        # Mock a response with rate limit exhausted
        responses.add(
            responses.GET,
            self.build_events_url("testuser"),
            json=[],
            status=200,
            headers={
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": "1234567890",
            }
        )

        # Should raise exception for rate limit
        with pytest.raises(Exception, match="GitHub API rate limit exceeded"):
            list(get_top_activities_by_repo_for("testuser"))

    @responses.activate
    def test_404_user_not_found(self):
        """Test handling of 404 when user doesn't exist"""

        # Mock a 404 response
        responses.add(
            responses.GET,
            self.build_events_url("nonexistentuser"),
            json={"message": "Not Found"},
            status=404
        )

        # Should raise HTTPError
        with pytest.raises(requests.HTTPError):
            list(get_top_activities_by_repo_for("nonexistentuser"))

    @responses.activate
    def test_500_server_error(self):
        """Test handling of server errors"""

        # Mock a 500 response
        responses.add(
            responses.GET,
            self.build_events_url("testuser"),
            json={"message": "Internal Server Error"},
            status=500
        )

        # Should raise HTTPError
        with pytest.raises(requests.HTTPError):
            list(get_top_activities_by_repo_for("testuser"))

    @responses.activate
    def test_connection_error(self):
        """Test handling of connection errors"""

        # responses can simulate connection errors
        responses.add(
            responses.GET,
            self.build_events_url("testuser"),
            body=requests.ConnectionError("Connection refused")
        )

        # Should raise ConnectionError
        with pytest.raises(requests.ConnectionError):
            list(get_top_activities_by_repo_for("testuser"))

    @responses.activate
    def test_timeout_error(self):
        """Test handling of timeout errors"""

        # Simulate a timeout
        responses.add(
            responses.GET,
            self.build_events_url("testuser"),
            body=requests.Timeout("Request timed out")
        )

        # Should raise Timeout
        with pytest.raises(requests.Timeout):
            list(get_top_activities_by_repo_for("testuser"))

    @responses.activate
    def test_mixed_owned_and_contributed_repos(self):
        """Test scenario with both owned and contributed repositories"""

        events = [
            # User's own repos
            EventBuilder.push_event("testuser/my-project"),
            EventBuilder.push_event("testuser/my-project"),
            EventBuilder.merge_event("testuser/my-project"),
            EventBuilder.push_event("testuser/another-project"),

            # Contributing to other repos
            EventBuilder.pull_request_event("opensource/popular-lib"),
            EventBuilder.pull_request_review_event("opensource/popular-lib"),
            EventBuilder.issue_comment_event("opensource/popular-lib"),
            EventBuilder.pull_request_review_comment_event("opensource/popular-lib"),

            EventBuilder.issue_comment_event("company/team-repo"),
            EventBuilder.pull_request_event("company/team-repo"),

            # Unmapped events (should be ignored)
            EventBuilder.unmapped_event("random/repo", "WatchEvent"),
            EventBuilder.unmapped_event("random/repo", "ForkEvent"),
        ]

        responses.add(
            responses.GET,
            self.build_events_url("testuser"),
            json=events,
            status=200,
            headers={"X-RateLimit-Remaining": "5000"}
        )

        results = list(get_top_activities_by_repo_for("testuser"))

        # Should have 4 repos (random/repo ignored due to unmapped events)
        assert len(results) == 4

        # Check owned repos
        owned_repos = [r for r in results if r.owned]
        assert len(owned_repos) == 2
        assert all(r.name.startswith("testuser/") for r in owned_repos)

        # Check contributed repos
        contributed_repos = [r for r in results if not r.owned]
        assert len(contributed_repos) == 2
        assert all(not r.name.startswith("testuser/") for r in contributed_repos)

    @responses.activate
    def test_empty_user_activity(self):
        """Test user with no public activity"""

        responses.add(
            responses.GET,
            self.build_events_url("inactiveuser"),
            json=[],
            status=200,
            headers={"X-RateLimit-Remaining": "5000"}
        )

        results = list(get_top_activities_by_repo_for("inactiveuser"))

        assert results == []

    @responses.activate
    def test_malformed_event_structure(self):
        """Test handling of events with unexpected structure"""

        events = [
            # Normal event
            EventBuilder.push_event("user/repo1"),
            # Event missing repo name
            {"type": "PushEvent", "repo": {}, "payload": {}},
            # Event missing type
            {"repo": {"name": "user/repo2"}, "payload": {}},
            # Normal event
            EventBuilder.pull_request_event("user/repo1"),
        ]

        responses.add(
            responses.GET,
            self.build_events_url("testuser"),
            json=events,
            status=200,
            headers={"X-RateLimit-Remaining": "5000"}
        )

        # This test verifies the code handles malformed events gracefully
        # It should process valid events and skip invalid ones
        try:
            results = list(get_top_activities_by_repo_for("testuser"))
            # Should only process valid events for repo1
            assert len(results) == 1
            assert results[0].name == "user/repo1"
        except (KeyError, TypeError):
            # If the code doesn't handle malformed events, it will raise an exception
            pytest.fail("Code doesn't handle malformed event structures gracefully")


class TestComplexPaginationScenarios(IntegrationTestBase):
    """Test complex pagination scenarios"""

    @responses.activate
    def test_pagination_with_changing_rate_limits(self):
        """Test pagination with decreasing rate limits across pages"""

        # Create events for multiple pages
        events_per_page = 100
        total_pages = 5

        for page in range(1, total_pages + 1):
            # Create events for this page
            events = [
                EventBuilder.push_event(f"testuser/repo-{i % 10}")
                for i in range(page * events_per_page, (page + 1) * events_per_page)
            ]

            # Calculate remaining rate limit (simulating consumption)
            remaining = str(5000 - page)

            # Determine if there's a next page
            has_next = page < total_pages

            # Build URL for this page
            url = self.build_events_url("testuser", page if page > 1 else None)

            # Add response
            responses.add(
                responses.GET,
                url,
                json=events if remaining != "0" else [],  # Empty if rate limited
                status=200,
                headers={
                    **self.build_link_header("testuser", page, has_next),
                    "X-RateLimit-Remaining": remaining,
                }
            )

        # Call our function
        results = list(get_top_activities_by_repo_for("testuser"))

        # Should have processed all pages and found 10 repos
        assert len(results) == 10

        # Verify all API calls were made
        assert len(responses.calls) == total_pages

    @responses.activate
    def test_pagination_stops_on_empty_response(self):
        """Test that pagination stops when an empty response is received"""

        # First page with events
        responses.add(
            responses.GET,
            self.build_events_url("testuser"),
            json=[EventBuilder.push_event("testuser/repo") for _ in range(100)],
            status=200,
            headers={
                **self.build_link_header("testuser", 1, has_next=True),
                "X-RateLimit-Remaining": "5000",
            }
        )

        # Second page is empty but still has Link header (edge case)
        responses.add(
            responses.GET,
            self.build_events_url("testuser", 2),
            json=[],
            status=200,
            headers={
                **self.build_link_header("testuser", 2, has_next=True),
                "X-RateLimit-Remaining": "4999",
            }
        )

        # Third page (should not be called if implementation is smart)
        responses.add(
            responses.GET,
            self.build_events_url("testuser", 3),
            json=[EventBuilder.push_event("testuser/repo2")],
            status=200,
            headers={"X-RateLimit-Remaining": "4998"}
        )

        # Call our function
        results = list(get_top_activities_by_repo_for("testuser"))

        # Should have one repo from first page
        assert len(results) == 1
        assert results[0].name == "testuser/repo"

        # Depending on implementation, might call page 2 and stop, or all 3 pages
        # This tests the actual behavior
        assert len(responses.calls) >= 2  # At least first two pages


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
