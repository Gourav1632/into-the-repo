import os
import requests
from urllib.parse import urlparse
from typing import Dict,Any
from dotenv import load_dotenv
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from src.shared.progress import progress_data

env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

GITHUB_API_BASE = "https://api.github.com"

def extract_owner_repo(repo_url):
    parts = urlparse(repo_url).path.strip("/").split("/")
    if len(parts) >= 2:
        owner = parts[0]
        repo = parts[1].replace(".git", "")
        return owner, repo
    raise ValueError("Invalid GitHub URL format")

def get_repo_tree(owner, repo, branch):
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    headers = {
        "Accept": "application/vnd.github+json"
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()["tree"]

def download_file(owner, repo, path, branch):
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.text


def get_file_git_info(owner: str, repo: str, branch: str, filepath: str) -> Dict[str, Any]:
    url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    params = {
        "path": filepath,
        "sha": branch,
        "per_page": 10  # limit recent commits fetched
    }

    headers = {
        "Accept": "application/vnd.github+json"
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    response = requests.get(url, params=params, headers=headers)
    if response.status_code != 200:

        print(f"GitHub API error: {response.status_code} {response.text}")
        return {
            "commit_count": 0,
            "last_modified": None,
            "recent_commits": []
        }

    commits = response.json()
    commit_count = len(commits)

    if commit_count == 0:
        return {
            "commit_count": 0,
            "last_modified": None,
            "recent_commits": []
        }

    recent_commits = []
    for c in commits:
        commit = c.get("commit", {})
        author = commit.get("author", {})
        recent_commits.append({
            "sha": c.get("sha"),
            "message": commit.get("message"),
            "author": author.get("name"),
            "date": author.get("date")
        })

    last_modified = recent_commits[0]["date"]

    # To get total commit count for the file, we might need to paginate or do a separate count
    # But GitHub API doesn't provide total count directly for file commits.
    # For now, we use the number of commits fetched or estimate from pagination headers.
    link_header = response.headers.get("Link")
    if link_header:
        import re
        match = re.search(r'&page=(\d+)>; rel="last"', link_header)
        if match:
            last_page_num = int(match.group(1))
            # commits per page is 10, so estimate total count
            commit_count = last_page_num * 10

    return {
        "commit_count": commit_count,
        "last_modified": last_modified,
        "recent_commits": recent_commits
    }

def get_repo_git_analysis(repo: str, branch: str ,request_id:str) -> Dict[str, Any]:
    print("Getting git analysis...")
    owner, repo_name = extract_owner_repo(repo)
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    base_url = f"https://api.github.com/repos/{owner}/{repo_name}"

    # 1. Get total commits count (from commits API with per_page=1)
    commits_resp = requests.get(f"{base_url}/commits", headers=headers, params={"sha": branch, "per_page": 1})
    commits_resp.raise_for_status()
    link_header = commits_resp.headers.get("Link", "")
    total_commits = None
    if link_header:
        import re
        match = re.search(r'&page=(\d+)>; rel="last"', link_header)
        if match:
            total_commits = int(match.group(1))
    if total_commits is None:
        total_commits = 1
    print("Total commits fetched: ",total_commits)


    # 2. Fetch recent 50 commits only for analysis
    commits_resp = requests.get(f"{base_url}/commits", headers=headers, params={"sha": branch, "per_page": 50})
    commits_resp.raise_for_status()
    recent_commits = commits_resp.json()

    # Prepare stats from recent commits
    commit_activity = defaultdict(int)
    file_activity = defaultdict(int)
    author_stats = defaultdict(int)
    recent_commit_summaries = []

    for i, commit in enumerate(recent_commits):
        
        date_str = commit["commit"]["author"]["date"]
        date = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ").date()
        commit_activity[str(date)] += 1

        author = commit["commit"]["author"]["name"]
        author_stats[author] += 1

        sha = commit["sha"]
        message = commit["commit"]["message"]
        if(i < 10):
            if total_commits <= 50:
                progress_data[request_id] = f"Seriously, bro? You want me to analyze just {total_commits} commits?"
            elif total_commits > 50 and total_commits < 500:
                progress_data[request_id] = f"Digging through some history! Found about {total_commits} commits."
            else:
                progress_data[request_id] = f"{total_commits} commits? Yeah, I don't have all day. I'll just look at the last 50."
        else:                
            if "final commit" in message or "last commit" in message:
                progress_data[request_id] = f"Ah, the {message}. Heard that one before. Let's see how long *this* one lasts."
            else:
                progress_data[request_id] = f"Analysing commit {sha}..."

        # Fetch files changed for this commit
        detail_resp = requests.get(f"{base_url}/commits/{sha}", headers=headers)
        if detail_resp.status_code == 200:
            files = detail_resp.json().get("files", [])
            for f in files:
                file_activity[f["filename"]] += 1

        # Keep only first 10 recent commits details (for preview)
        if len(recent_commit_summaries) < 10:
            recent_commit_summaries.append({
                "sha": sha,
                "message": commit["commit"]["message"],
                "author": author,
                "date": date_str
            })

    return {
        "repo": repo_name,
        "owner": owner,
        "default_branch": branch,
        "total_commits_fetched": total_commits,  # total commits in repo
        "most_changed_files": sorted(
            [{"file": fname, "changes": cnt} for fname, cnt in file_activity.items()],
            key=lambda x: x["changes"],
            reverse=True
        )[:10],
        "top_contributors": sorted(
            [{"name": name, "commits": count} for name, count in author_stats.items()],
            key=lambda x: x["commits"],
            reverse=True
        )[:5],
        "commit_activity_by_day": commit_activity,
        "recent_commits": recent_commit_summaries,
        "first_commit_date": recent_commits[-1]["commit"]["author"]["date"] if recent_commits else None,
        "last_commit_date": recent_commits[0]["commit"]["author"]["date"] if recent_commits else None,
    }


def is_repo_private(repo_url: str) -> bool:
    """
    Checks whether a GitHub repository is private or not.
    Returns True if private, False if public.
    """
    try:
        owner, repo_name = extract_owner_repo(repo_url)
        api_url = f"https://api.github.com/repos/{owner}/{repo_name}"

        headers = {
            "Accept": "application/vnd.github+json"
        }
        if GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

        response = requests.get(api_url, headers=headers)

        if response.status_code == 404:
            return True  
        elif response.status_code == 200:
            return response.json().get("private", True) 
        else:
            print(f"Unexpected status code {response.status_code}: {response.text}")
            return True  # Fail-safe: assume private

    except Exception as e:
        print(f"Error checking repo visibility: {e}")
        return True  # Fail-safe


def branch_exists(repo_url: str, branch: str = None) -> bool:
    """
    Checks whether a branch exists in the given GitHub repository.
    Returns True if branch exists, False otherwise.
    """
    print(f"Checking branch existence for repo: {repo_url}, branch: {branch}")
    try:
        owner, repo_name = extract_owner_repo(repo_url)
        api_url = f"https://api.github.com/repos/{owner}/{repo_name}/branches/{branch}"

        headers = {}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

        response = requests.get(api_url, headers=headers)

        if response.status_code == 200:
            return True
        elif response.status_code == 404:
            return False
        else:
            print(f"Unexpected status code {response.status_code}: {response.text}")
            return False

    except Exception as e:
        print(f"Error checking branch existence: {e}")
        return False

