import os
import subprocess
import shutil
import requests
from urllib.parse import urlparse
from typing import Dict, Any, Optional, Tuple
from dotenv import load_dotenv
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from tempfile import TemporaryDirectory, mkdtemp
from src.shared.progress import progress_data
from src.core.logging import get_logger

logger = get_logger(__name__)

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


def clone_repo_shallow(repo_url: str, branch: str = "main", depth: int = 1) -> str:
    """
    Clone a repository using shallow cloning (--depth) for better performance.
    Returns the path to the cloned repository.
    
    This reduces repository ingestion time by ~90% for large repositories.
    
    Args:
        repo_url: GitHub repository URL
        branch: Branch to clone (default: main)
        depth: Depth of clone history to fetch (default: 1, only latest commit)
    
    Returns:
        Path to the cloned repository
    
    Raises:
        subprocess.CalledProcessError: If git clone fails
    """
    try:
        # Create temporary directory using mkdtemp() instead of TemporaryDirectory()
        # TemporaryDirectory() auto-deletes when the object is garbage collected,
        # which happens immediately after this function returns
        clone_path = mkdtemp(prefix="repo_clone_")
        
        logger.info(f"Starting shallow clone of {repo_url} with depth={depth}")
        
        # Build git clone command with shallow clone option
        git_url = repo_url if repo_url.endswith(".git") else f"{repo_url}.git"
        
        cmd = [
            "git",
            "clone",
            "--depth", str(depth),
            "--branch", branch,
            "--single-branch",
            git_url,
            clone_path
        ]
        
        # Execute git clone
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode,
                cmd,
                result.stdout,
                result.stderr
            )
        
        logger.info(f"Successfully cloned repository to {clone_path}")
        return clone_path
        
    except subprocess.TimeoutExpired:
        logger.error(f"Clone operation timed out for {repo_url}")
        raise
    except subprocess.CalledProcessError as e:
        logger.error(f"Git clone failed: {e.stderr}")
        raise
    except Exception as e:
        logger.error(f"Error during shallow clone: {e}")
        raise


def get_repo_files_from_clone(clone_path: str, file_extensions: Optional[list] = None) -> Dict[str, str]:
    """
    Extract files from a cloned repository.
    Optionally filter by file extensions.
    
    Args:
        clone_path: Path to the cloned repository
        file_extensions: List of extensions to include (e.g., ['.py', '.js', '.ts'])
    
    Returns:
        Dictionary mapping file path to file content
    """
    files_dict = {}
    clone_dir = Path(clone_path)
    
    try:
        # Walk through all files in the cloned directory
        for file_path in clone_dir.rglob("*"):
            if file_path.is_file():
                # Skip git directory and hidden files
                if ".git" in file_path.parts:
                    continue
                
                # Filter by extensions if provided
                if file_extensions:
                    if file_path.suffix not in file_extensions:
                        continue
                
                # Get relative path and file content
                relative_path = str(file_path.relative_to(clone_dir))
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        files_dict[relative_path] = content
                except Exception as e:
                    logger.warning(f"Could not read file {relative_path}: {e}")
        
        return files_dict
        
    except Exception as e:
        logger.error(f"Error extracting files from clone: {e}")
        return files_dict

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


def get_file_git_info(local_repo_path: str, filepath: str, branch: str = "HEAD") -> Dict[str, Any]:
    """
    Get git information for a specific file using local git commands.
    
    Args:
        local_repo_path: Path to the locally cloned repository
        filepath: Path to the file relative to repository root
        branch: Branch name (default: HEAD)
    
    Returns:
        Dictionary with commit count, last_modified date, and recent commits for the file
    """
    try:
        # Get the number of commits that touched this file
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD", "--", filepath],
            cwd=local_repo_path,
            capture_output=True,
            text=True,
            timeout=10
        )
        commit_count = int(result.stdout.strip()) if result.returncode == 0 else 0
        
    except Exception as e:
        logger.warning(f"Failed to get commit count for {filepath}: {e}")
        commit_count = 0
    
    try:
        # Get the last 10 commits for this file
        result = subprocess.run(
            ["git", "log", "-10", "--format=%H|%an|%aI|%s", "--", filepath],
            cwd=local_repo_path,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        recent_commits = []
        last_modified = None
        
        if result.returncode == 0 and result.stdout.strip():
            for i, line in enumerate(result.stdout.strip().split('\n')):
                if not line.strip():
                    continue
                
                try:
                    parts = line.split('|')
                    if len(parts) >= 4:
                        sha, author, date_str, message = parts[0], parts[1], parts[2], parts[3]
                        
                        recent_commits.append({
                            "sha": sha,
                            "message": message,
                            "author": author,
                            "date": date_str
                        })
                        
                        if i == 0:
                            last_modified = date_str
                except Exception as e:
                    logger.warning(f"Failed to parse commit line: {e}")
            
        return {
            "commit_count": commit_count,
            "last_modified": last_modified,
            "recent_commits": recent_commits
        }
        
    except Exception as e:
        logger.warning(f"Failed to get git log for {filepath}: {e}")
        return {
            "commit_count": commit_count,
            "last_modified": None,
            "recent_commits": []
        }

def get_repo_git_analysis(local_repo_path: str, repo_url: str, branch: str, request_id: str) -> Dict[str, Any]:
    """
    Analyze git repository using local git commands instead of HTTP API calls.
    This is much faster and doesn't hit rate limits.
    
    Args:
        local_repo_path: Path to the locally cloned repository
        repo_url: GitHub URL (used only for extracting repo name and owner)
        branch: Branch to analyze
        request_id: Request ID for progress tracking
    
    Returns:
        Dictionary with git analysis stats
    """
    logger.info(f"Starting git analysis for local repo at {local_repo_path}")
    
    try:
        owner, repo_name = extract_owner_repo(repo_url)
    except:
        repo_name = Path(local_repo_path).name
        owner = "unknown"
    
    # Get total commit count
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=local_repo_path,
            capture_output=True,
            text=True,
            timeout=30
        )
        total_commits = int(result.stdout.strip()) if result.returncode == 0 else 0
        logger.info(f"Total commits: {total_commits}")
    except Exception as e:
        logger.warning(f"Failed to get total commits: {e}")
        total_commits = 0
    
    # Get last 50 commits with detailed information
    try:
        result = subprocess.run(
            ["git", "log", "--max-count=50", "--format=%H|%an|%ae|%aI|%s"],
            cwd=local_repo_path,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            logger.error(f"Git log failed: {result.stderr}")
            return _get_empty_git_analysis(repo_name, owner, branch)
        
        commits_data = result.stdout.strip().split('\n')
        
    except Exception as e:
        logger.error(f"Failed to get git log: {e}")
        return _get_empty_git_analysis(repo_name, owner, branch)
    
    # Process commits
    commit_activity = defaultdict(int)
    file_activity = defaultdict(int)
    author_stats = defaultdict(int)
    recent_commit_summaries = []
    
    for i, commit_line in enumerate(commits_data):
        if not commit_line.strip():
            continue
        
        try:
            parts = commit_line.split('|')
            if len(parts) < 5:
                continue
            
            sha, author, email, date_str, message = parts[0], parts[1], parts[2], parts[3], parts[4]
            
            # Parse date and extract date part only
            try:
                date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                date_key = str(date_obj.date())
            except:
                date_key = date_str
            
            commit_activity[date_key] += 1
            author_stats[author] += 1
            
            # Update progress
            if i < 10:
                if total_commits <= 5:
                    progress_data[request_id] = f"Seriously, bro? You want me to analyze just {total_commits} commits?"
                elif total_commits <= 50:
                    progress_data[request_id] = f"Digging through some history! Found about {total_commits} commits."
                else:
                    progress_data[request_id] = f"{total_commits} commits? Yeah, I don't have all day. I'll just look at the last 50."
            else:
                progress_data[request_id] = f"Analysing commit {sha}..."
            
            # Get files changed in this commit
            try:
                file_result = subprocess.run(
                    ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", sha],
                    cwd=local_repo_path,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if file_result.returncode == 0:
                    for file_path in file_result.stdout.strip().split('\n'):
                        if file_path.strip():
                            file_activity[file_path.strip()] += 1
            except Exception as e:
                logger.warning(f"Failed to get files for commit {sha}: {e}")
            
            # Keep first 10 commits for preview
            if len(recent_commit_summaries) < 10:
                recent_commit_summaries.append({
                    "sha": sha,
                    "message": message,
                    "author": author,
                    "date": date_str
                })
                
        except Exception as e:
            logger.warning(f"Error processing commit {i}: {e}")
            continue
    
    return {
        "repo": repo_name,
        "owner": owner,
        "default_branch": branch,
        "total_commits_fetched": total_commits,
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
        "commit_activity_by_day": dict(commit_activity),
        "recent_commits": recent_commit_summaries,
        "first_commit_date": recent_commit_summaries[-1]["date"] if recent_commit_summaries else None,
        "last_commit_date": recent_commit_summaries[0]["date"] if recent_commit_summaries else None,
    }


def _get_empty_git_analysis(repo_name: str, owner: str, branch: str) -> Dict[str, Any]:
    """Return an empty git analysis structure when analysis fails."""
    return {
        "repo": repo_name,
        "owner": owner,
        "default_branch": branch,
        "total_commits_fetched": 0,
        "most_changed_files": [],
        "top_contributors": [],
        "commit_activity_by_day": {},
        "recent_commits": [],
        "first_commit_date": None,
        "last_commit_date": None,
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
            logger.warning(f"Unexpected status code {response.status_code}: {response.text}")
            return True  # Fail-safe: assume private

    except Exception as e:
        logger.error(f"Error checking repo visibility: {e}")
        return True  # Fail-safe


def branch_exists(repo_url: str, branch: str = None) -> bool:
    """
    Checks whether a branch exists in the given GitHub repository.
    Returns True if branch exists, False otherwise.
    """
    logger.debug(f"Checking branch existence for repo: {repo_url}, branch: {branch}")
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
            logger.warning(f"Unexpected status code {response.status_code}: {response.text}")
            return False

    except Exception as e:
        logger.error(f"Error checking branch existence: {e}")
        return False

