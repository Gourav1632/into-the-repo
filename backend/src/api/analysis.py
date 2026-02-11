from fastapi import APIRouter, BackgroundTasks, Header, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional
from fastapi.concurrency import run_in_threadpool
import asyncio
import os
import shutil
from src.services.analysis.ast_parser import parse_code
from src.services.analysis.per_file_graph_builder import build_per_file_graph, build_call_graph
from src.services.analysis.summarizer import analyze_code
from src.services.utilities.git_utils import get_repo_git_analysis, is_repo_private, branch_exists, clone_repo_shallow
from src.services.ai.ask_ai import askAI, reset_chat_history
from src.core.security import verify_token
from src.core.database import get_db
from src.models.database import RepoAnalysis, UserAnalysisHistory
from src.middleware.rate_limiter import limiter
from src.core.logging import get_logger
from sqlalchemy.orm import Session
import traceback
from fastapi.responses import StreamingResponse
from src.shared.progress import progress_data
from fastapi import Request
from src.tasks.worker import app as celery_app
from src.schemas.requests import AskRequest, RepoRequest, FileGraphRequest, VerifyRequest

router = APIRouter()
logger = get_logger(__name__)


async def get_current_user_from_header(authorization: Optional[str] = Header(None)):
    """
    Extract and verify user from Authorization header.
    
    Args:
        authorization: Authorization header value (Bearer token)
    
    Returns:
        User ID and token data if valid, None otherwise
    """
    if not authorization:
        return None
    
    try:
        # Extract token from "Bearer <token>" format
        if not authorization.startswith("Bearer "):
            return None
        
        token = authorization[7:]
        token_data = verify_token(token)
        
        if token_data is None:
            return None
        
        return token_data
    except Exception as e:
        print(f"Error extracting user from token: {e}")
        return None


# === Routes ===

@router.get("/api/progress")
async def progress(request:Request ,request_id: str):
    print(f"[DEBUG] /api/progress called with request_id: {request_id}")
    
    async def event_generator():
        print(f"[DEBUG] Starting SSE stream for request_id: {request_id}")
        last_message = None
        no_change_count = 0
        max_no_change = 240  # 60 seconds of no change before timeout (increased for large repos)
        iteration = 0
        
        while True:
            iteration += 1
            if await request.is_disconnected(): 
                print(f"[DEBUG] Client disconnected for request_id: {request_id}")
                break
            
            # Try to get detailed progress from progress_data first
            progress_msg = progress_data.get(request_id)
            
            # Fallback to Celery task state if no detailed progress
            if not progress_msg:
                task = celery_app.AsyncResult(request_id)
                
                if iteration % 10 == 0:  # Log every 5 seconds
                    print(f"[DEBUG] Task state: {task.state} (iteration {iteration})")
                
                if task.state == 'PROGRESS':
                    progress_msg = task.info.get('status', 'Processing...')
                elif task.state == 'SUCCESS':
                    progress_msg = 'done'
                elif task.state == 'FAILURE':
                    progress_msg = f'Error: {str(task.info)}'
                else:
                    progress_msg = 'Waiting...'
            
            if progress_msg != last_message:
                no_change_count = 0
                print(f"[DEBUG] Sending progress: {progress_msg}")
                if progress_msg == 'done':
                    print(f"[DEBUG] Analysis done, closing SSE stream for request_id: {request_id}")
                    yield "event: done\ndata: Analysis complete\n\n"
                    break
                else:
                    yield f"data: {progress_msg}\n\n"
                last_message = progress_msg
            else:
                no_change_count += 1
                if no_change_count > max_no_change:
                    # Send a heartbeat to keep connection alive
                    yield ": heartbeat\n\n"
            
            await asyncio.sleep(0.1)  # Reduced from 0.5s to catch more updates
        
        print(f"[DEBUG] SSE stream closed for request_id: {request_id}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Transfer-Encoding": "chunked",
        }
    )


@router.post("/api/verify")
async def verify_repo_branch(req: VerifyRequest):
    """
    Verify if the given repository is public and if the specified branch exists.
    """
    try:
        is_private_task = asyncio.create_task(run_in_threadpool(is_repo_private, req.repo_url))
        branch_exists_task = asyncio.create_task(run_in_threadpool(branch_exists, req.repo_url, req.branch))
        
        is_private, does_branch_exist = await asyncio.gather(is_private_task, branch_exists_task)

        if is_private:
            return {"success": False, "error": "Repository is private or inaccessible. Please ensure it is public."}

        if not does_branch_exist:
            return {"success": False, "error": f"Branch '{req.branch}' does not exist in the repository."}

        return {"success": True, "message": "Repository URL and branch are valid."}

    except Exception as e:
        traceback.print_exc()
        return {"success": False, "error": str(e)}



@router.post("/api/analyze")
@limiter.limit("5/minute")
async def get_ast(
    req: RepoRequest,
    request: Request,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Analyze a GitHub repository asynchronously using Celery.
    """
    request_id = req.request_id
    user_id: Optional[int] = None
    
    try:
        print(f"[DEBUG] /api/analyze called with request_id: {request_id}, repo: {req.repo_url}, branch: {req.branch}")
        logger.info(f"[DEBUG] /api/analyze called with request_id: {request_id}")
        
        # Extract user from Authorization header if provided
        if authorization:
            token_data = await get_current_user_from_header(authorization)
            if token_data:
                user_id = token_data.user_id
                logger.info(f"Analysis requested by user: {token_data.email}")
        
        print(f"[DEBUG] Queuing analysis task for {req.repo_url}")
        logger.info(f"Queuing analysis task for {req.repo_url}")
        
        # Queue the analysis task
        task = celery_app.send_task(
            'analyze_repository',
            args=[req.repo_url, req.branch, request_id],
            task_id=request_id
        )
        
        print(f"[DEBUG] Analysis task queued with task_id: {request_id}, task state: {task.state}")
        logger.info(f"Analysis task queued with task_id: {request_id}")
        
        return {
            "task_id": request_id,
            "status": "queued",
            "message": "Analysis task has been queued and will be processed shortly."
        }
        
    except Exception as e:
        print(f"[DEBUG] Error queuing analysis task: {e}")
        logger.error(f"Error queuing analysis task: {e}", exc_info=True)
        return {
            "error": str(e),
            "task_id": request_id
        }


@router.get("/api/analyze/status/{task_id}")
async def get_analysis_status(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    Get the status of a repository analysis task.
    
    Args:
        task_id: The task ID returned from /api/analyze
        db: Database session
    
    Returns:
        Dictionary with task status and results (if completed)
    """
    try:
        print(f"[DEBUG] /api/analyze/status called for task_id: {task_id}")
        task = celery_app.AsyncResult(task_id)
        print(f"[DEBUG] Task state: {task.state}")
        
        if task.state == 'PENDING':
            print(f"[DEBUG] Task is still pending")
            return {"status": "pending", "task_id": task_id}
        
        elif task.state == 'PROGRESS':
            print(f"[DEBUG] Task is in progress: {task.info}")
            return {
                "status": "in-progress",
                "task_id": task_id,
                "progress": task.info.get('status', 'Processing...')
            }
        
        elif task.state == 'SUCCESS':
            print(f"[DEBUG] Task completed successfully")
            result = task.result
            print(f"[DEBUG] Result type: {type(result)}, keys: {result.keys() if isinstance(result, dict) else 'N/A'}")
            
            return {
                "status": "completed",
                "task_id": task_id,
                "result": result
            }
        
        elif task.state == 'FAILURE':
            print(f"[DEBUG] Task failed: {task.info}")
            return {
                "status": "failed",
                "task_id": task_id,
                "error": str(task.info)
            }
        
        else:
            print(f"[DEBUG] Task in unknown state: {task.state}")
            return {
                "status": task.state.lower(),
                "task_id": task_id
            }
    
    except Exception as e:
        print(f"[DEBUG] Error in /api/analyze/status: {e}")
        logger.error(f"Error getting task status: {e}")
        return {
            "status": "error",
            "task_id": task_id,
            "error": str(e)
        }



@router.post("/api/file")
async def generate_file_graph(req: FileGraphRequest):
    print("Request for file graph...")

    file_graph_task = asyncio.create_task(run_in_threadpool(build_per_file_graph, req.file_path, req.file_ast))
    call_graph_task = asyncio.create_task(run_in_threadpool(build_call_graph, req.file_ast))
    analysis_task = asyncio.create_task(run_in_threadpool(analyze_code, req.repo_url, req.branch, req.file_path))

    file_graph, call_graph, analysis = await asyncio.gather(file_graph_task, call_graph_task, analysis_task)

    return {
        "file_path": req.file_path,
        "file_graph": file_graph,
        "call_graph": call_graph,
        "analysis": analysis
    }


@router.get("/api/user/history")
async def get_user_history(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Get analysis history for the authenticated user.
    
    Args:
        authorization: Bearer token for authentication
        db: Database session
    
    Returns:
        List of analysis history records with repository and analysis details
    """
    if not authorization:
        return {"error": "Authorization required"}
    
    token_data = await get_current_user_from_header(authorization)
    if not token_data:
        return {"error": "Invalid or expired token"}
    
    try:
        history_records = db.query(UserAnalysisHistory).filter(
            UserAnalysisHistory.user_id == token_data.user_id
        ).order_by(UserAnalysisHistory.analyzed_at.desc()).all()
        
        history_list = []
        for record in history_records:
            repo_analysis = record.repo_analysis
            history_list.append({
                "id": record.id,
                "repo_url": repo_analysis.repo_url,
                "branch": repo_analysis.branch,
                "analyzed_at": record.analyzed_at.isoformat() if record.analyzed_at else None,
                "notes": record.notes,
                "repo_analysis_id": repo_analysis.id
            })
        
        return {"history": history_list}
    
    except Exception as e:
        print(f"Error retrieving user history: {e}")
        return {"error": str(e)}


@router.post("/api/user/history/notes")
async def update_history_notes(
    history_id: int,
    notes: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Update notes for an analysis history record.
    
    Args:
        history_id: ID of the history record
        notes: New notes to save
        authorization: Bearer token for authentication
        db: Database session
    
    Returns:
        Success/error message
    """
    if not authorization:
        return {"error": "Authorization required"}
    
    token_data = await get_current_user_from_header(authorization)
    if not token_data:
        return {"error": "Invalid or expired token"}
    
    try:
        history = db.query(UserAnalysisHistory).filter(
            UserAnalysisHistory.id == history_id,
            UserAnalysisHistory.user_id == token_data.user_id
        ).first()
        
        if not history:
            return {"error": "History record not found"}
        
        history.notes = notes
        db.commit()
        
        return {"message": "Notes updated successfully"}
    
    except Exception as e:
        print(f"Error updating notes: {e}")
        return {"error": str(e)}


@router.post("/api/ask")
async def ask_route(req: AskRequest, db: Session = Depends(get_db)):
    """
    AI-powered code assistant endpoint with Redis-backed chat history.
    
    Features:
    - Maintains conversation context across requests via Redis
    - 1-hour TTL for chat sessions (auto-cleanup)
    - Optional history reset for starting fresh conversations
    - Semantic search for relevant code snippets (if repo_analysis_id provided)
    
    Args:
        req: AskRequest with question, code, history_id, reset flag, and optional repo_analysis_id
        db: Database session
    
    Returns:
        Dictionary with answer, history_id, and optional error
    """
    print("Requesting AI help...")
    history_id = req.history_id or f"{req.question[:20]}-{hash(req.code)}"

    if req.reset:
        print(f"History reset requested for history_id: {history_id}")
        reset_chat_history(history_id)
        return {"message": "Conversation history reset. Start fresh!"}

    response = await run_in_threadpool(askAI, req.question, req.code, history_id)
    return response
