"""
Celery worker for handling long-running analysis tasks.

This module defines async tasks for repository cloning, parsing, and analysis
that run in background worker processes to prevent blocking the API.
"""

import os
import shutil
from pathlib import Path
from dotenv import load_dotenv
from celery import Celery
from src.services.utilities.git_utils import clone_repo_shallow, get_repo_git_analysis
from src.services.analysis.ast_parser import parse_code

from src.core.logging import get_logger
from src.core.database import SessionLocal
from src.models.database import RepoAnalysis
from src.shared.progress import progress_data

logger = get_logger(__name__)

# Load environment variables
env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path)

# Initialize Celery
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

app = Celery(
    'into_the_repo',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['src.tasks.worker']
)

# Configure Celery
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes hard limit
    task_soft_time_limit=25 * 60,  # 25 minutes soft limit
    result_expires=3600,  # Results expire after 1 hour
)


@app.task(name='analyze_repository', bind=True)
def analyze_repository(self, repo_url: str, branch: str, request_id: str):
    """
    Analyze a GitHub repository asynchronously.
    
    This task:
    1. Clones the repository locally
    2. Parses the code to extract AST
    3. Analyzes git history
    4. Saves results to database
    5. Returns the combined analysis
    
    Args:
        repo_url: GitHub repository URL
        branch: Branch to analyze
        request_id: Request ID for tracking progress
    
    Returns:
        Dictionary with repo_analysis and git_analysis
    """
    db = SessionLocal()
    local_repo_path = None
    
    try:
        self.update_state(state='PROGRESS', meta={'status': 'Cloning repository...'})
        progress_data[request_id] = 'Initializing scan...'
        print(f"[DEBUG] Worker starting: repo={repo_url}, branch={branch}, request_id={request_id}")
        logger.info(f"Starting analysis task for {repo_url} (request_id: {request_id})")
        
        # Clone repository
        print(f"[DEBUG] Cloning repository...")
        local_repo_path = clone_repo_shallow(repo_url, branch)
        print(f"[DEBUG] Repository cloned to: {local_repo_path}")
        logger.info(f"Cloned {repo_url} to {local_repo_path}")
        
        # Parse code
        print(f"[DEBUG] Starting code parsing...")
        repo_analysis = parse_code(local_repo_path, repo_url, branch, request_id)
        print(f"[DEBUG] Code parsing complete, found {len(repo_analysis)} files")
        
        progress_data[request_id] = 'Analysing git history...'
        self.update_state(state='PROGRESS', meta={'status': 'Analyzing git history...'})
        logger.info(f"Parsed code for {repo_url}")
        
        # Get git analysis
        print(f"[DEBUG] Starting git analysis...")
        git_analysis = get_repo_git_analysis(local_repo_path, repo_url, branch, request_id)
        print(f"[DEBUG] Git analysis complete")
        logger.info(f"Completed analysis for {repo_url}")
        
        # Save to database
        try:
            # Check if repo analysis already exists
            existing = db.query(RepoAnalysis).filter(
                RepoAnalysis.repo_url == repo_url,
                RepoAnalysis.branch == branch
            ).first()
            
            if not existing:
                # Create new repo analysis record
                analysis_record = RepoAnalysis(
                    repo_url=repo_url,
                    branch=branch,
                    repo_analysis=repo_analysis,
                    git_analysis=git_analysis
                )
                db.add(analysis_record)
                db.commit()
                db.refresh(analysis_record)
                repo_analysis_id = analysis_record.id
            else:
                # Update existing record
                existing.repo_analysis = repo_analysis
                existing.git_analysis = git_analysis
                db.commit()
                repo_analysis_id = existing.id
            
            logger.info(f"Analysis saved to database for {repo_url}")
            
        except Exception as e:
            logger.error(f"Failed to save analysis to database: {e}")
            db.rollback()
        
        # Mark progress as done before returning
        progress_data[request_id] = "Putting the final pieces. Hope it was worth the wait (it probably wasn't)."
        logger.info(f"Analysis completed for {repo_url}")
        
        # Small delay to ensure client sees final message
        import time
        time.sleep(0.5)
        
        progress_data[request_id] = "done"
        
        # Log the structure of what we're returning
        print(f"[DEBUG] Returning analysis with repo_analysis keys: {repo_analysis.keys() if isinstance(repo_analysis, dict) else 'not a dict'}")
        print(f"[DEBUG] Returning analysis with git_analysis type: {type(git_analysis)}")
        
        # Return the combined analysis
        return {
            'repo_analysis': repo_analysis,
            'git_analysis': git_analysis,
            'repo_url': repo_url,
            'branch': branch,
            'request_id': request_id
        }
        
    except Exception as e:
        print(f"[DEBUG] Error analyzing repository {repo_url}: {e}")
        logger.error(f"Error analyzing repository {repo_url}: {e}", exc_info=True)
        progress_data[request_id] = f"❌ Error: {str(e)}"
        self.update_state(
            state='FAILURE',
            meta={'error': str(e)}
        )
        raise
        
    finally:
        # Cleanup temporary repository
        if local_repo_path and os.path.exists(local_repo_path):
            try:
                print(f"[DEBUG] Cleaning up temp repo at: {local_repo_path}")
                shutil.rmtree(local_repo_path)
                logger.info(f"Cleaned up temporary repository: {local_repo_path}")
                print(f"[DEBUG] Temp repo cleaned up")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp repo at {local_repo_path}: {e}")
        
        # Close database session
        print(f"[DEBUG] Closing database session")
        db.close()
        
        # Clean up progress data after a delay to ensure client gets final message
        # (This is optional but helps prevent memory leakage from old requests)
        # progress_data.pop(request_id, None)


@app.task(name='clone_repository', bind=True)
def clone_repository(self, repo_url: str, branch: str = 'main'):
    """
    Clone a repository asynchronously.
    
    Args:
        repo_url: GitHub repository URL
        branch: Branch to clone (default: main)
    
    Returns:
        Path to the cloned repository
    """
    try:
        self.update_state(state='PROGRESS', meta={'status': 'Cloning...'})
        logger.info(f"Starting clone task for {repo_url}")
        
        local_repo_path = clone_repo_shallow(repo_url, branch)
        
        logger.info(f"Clone completed: {local_repo_path}")
        return {'local_repo_path': local_repo_path}
        
    except Exception as e:
        logger.error(f"Error cloning repository {repo_url}: {e}", exc_info=True)
        self.update_state(
            state='FAILURE',
            meta={'error': str(e)}
        )
        raise


@app.task(name='health_check')
def health_check():
    """
    Simple health check task to verify worker is responding.
    """
    return {'status': 'healthy', 'worker': 'active'}
