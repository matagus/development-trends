# Development Trends for Github API

![CI badge](https://github.com/matagus/development-trends/actions/workflows/ci.yml/badge.svg)
[![codecov](https://codecov.io/gh/matagus/development-trends/graph/badge.svg?token=a64SxEDQk0)](https://codecov.io/gh/matagus/development-trends)

A library to get visibility into engineering activity so that we can track development trends across projects. It analyzes recent GitHub activity for a user and provides insights into their top activities by repository.

## 📝 Important Note

**Please read the `questions.txt` file** for important notes, implementation decisions, and questions about the project requirements.

## Features

- Fetches recent GitHub events for a user (up to 30 days)
- Groups activities by repository
- Identifies top 3 activity types per repository
- Distinguishes between owned and contributed repositories
- Maps GitHub events to meaningful activity types (commits, pull requests, merges, comments)

## Requirements

- Python 3.10 or higher
- pip or hatch for package management

## Installation

### Local Installation

#### Using pip (recommended for users)

```bash
# Clone the repository
git clone https://github.com/matagus/development-trends.git
cd development-trends

# Install the package
pip install .

# Or install in editable mode for development
pip install -e .
```

#### Using hatch (recommended for developers)

```bash
# Clone the repository
git clone https://github.com/matagus/development-trends.git
cd development-trends

# Create a virtual environment and install dependencies
hatch shell
```

## Usage

### Command Line Interface

You can run the script directly from the command line to analyze a GitHub user's activity:

```bash
# Run directly with Python
python development_trends.py <github_username>

# Example
python development_trends.py torvalds
```

The output will be a JSON list of repositories with their top activities:

```json
[
  {
    "name": "user/repo",
    "top_activities": ["commits", "pull requests", "comments"],
    "owned": true
  },
  ...
]
```

### Using as a Python Library

You can also import and use the library in your Python code:

```python
from development_trends import get_top_activities_by_repo_for

# Get an iterator of repo activities for a user
username = "torvalds"
for repo_activities in get_top_activities_by_repo_for(username):
    print(f"Repository: {repo_activities.name}")
    print(f"Top Activities: {repo_activities.top_activities}")
    print(f"Owned by user: {repo_activities.owned}")
    print("---")

# Or collect all results as a list
all_activities = list(get_top_activities_by_repo_for(username))
```

#### Available Functions and Classes

- `get_top_activities_by_repo_for(username: str)`: Returns an iterator of `RepoTopActivities` objects
- `RepoTopActivities`: Data class with attributes:
  - `name`: Repository full name (owner/repo)
  - `top_activities`: List of top 3 activity types
  - `owned`: Boolean indicating if the user owns the repository
- `map_event_to_activity(event: dict)`: Maps GitHub events to activity types

## Running Tests

### Using hatch (recommended)

```bash
# Run tests for all Python versions
hatch run test:test

# Run tests for a specific Python version
hatch run test.py3.12:test

# Run tests with coverage
hatch run test:cov

# View available test environments
hatch env show
```

### Using pytest directly

```bash
# Install test dependencies
pip install pytest responses coverage

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest test_development_trends.py
pytest test_integration.py

# Run with coverage
coverage run -m pytest
coverage report
```

## Development

### Project Structure

```
development-trends/
├── development_trends.py     # Main module with core functionality
├── github_client.py          # GitHub API client
├── test_development_trends.py # Unit tests
├── test_integration.py       # Integration tests
├── questions.txt             # Important notes and questions
├── pyproject.toml           # Project configuration
└── README.md                # This file
```

### Code Quality Tools

The project uses:
- `black` for code formatting
- `ruff` for linting
- `pre-commit` for git hooks

To set up pre-commit hooks:

```bash
pip install pre-commit
pre-commit install
```

## Limitations

- GitHub API rate limit: 60 requests per hour for unauthenticated requests
- Events are limited to the last 30 days
- Maximum of 300 events per user
- No authentication support (yet)
- No retry logic for network failures
- No caching of API responses

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests to ensure everything works
5. Submit a pull request

## License

BSD License (see LICENSE file for details)

## Author

Matias Agustin Mendez (matagus@gmail.com)
