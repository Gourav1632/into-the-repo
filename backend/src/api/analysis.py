from fastapi import APIRouter, BackgroundTasks, Header, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional
from fastapi.concurrency import run_in_threadpool
import asyncio
from src.services.ast_parser import parse_code
from src.services.per_file_graph_builder import build_per_file_graph, build_call_graph
from src.services.summarizer import analyze_code
from src.services.git_utils import get_repo_git_analysis, is_repo_private, branch_exists
from src.services.ask_ai import askAI, reset_chat_history
from src.auth import verify_token
from src.database import get_db
from src.models import RepoAnalysis, UserAnalysisHistory
from src.rate_limiter import limiter
from sqlalchemy.orm import Session
import traceback
from fastapi.responses import StreamingResponse
from src.shared.progress import progress_data
from fastapi import Request

router = APIRouter()

# === Request Schemas ===


class AskRequest(BaseModel):
    question: str
    code: str
    history_id: Optional[str] = None
    reset: Optional[bool] = False

class RepoRequest(BaseModel):
    repo_url: str
    branch: str 
    request_id: str

class FileGraphRequest(BaseModel):
    file_path: str
    file_ast: Dict[str, Any]
    repo_url: str
    branch: str

class VerifyRequest(BaseModel):
    repo_url: str
    branch: str


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
    async def event_generator():
        last_message = None
        while True:
            if await request.is_disconnected(): 
                break  # ✅ client closed browser tab or stream
            progress = progress_data.get(request_id, "Waiting...")
            if progress == "done":
                break  # ✅ Exit the loop when done
            if progress != last_message:
                yield f"data: {progress}\n\n"
                last_message = progress
                await asyncio.sleep(1)

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
    background_tasks: BackgroundTasks,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Analyze a GitHub repository and return AST and git analysis.
    
    **Rate Limited**: 5 requests per minute per IP address
    
    Optional user authentication via Authorization header (Bearer token)
    allows saving analysis history to user's account.
    
    Args:
        req: RepoRequest with repo_url, branch, request_id
        request: FastAPI request object (for rate limiting)
        background_tasks: Background task queue
        authorization: Optional Bearer token for authentication
        db: Database session
    
    Returns:
        Dictionary with repo_analysis and git_analysis, plus optional user history save
    """
    request_id = req.request_id
    user_id: Optional[int] = None
    
    try:
        # Extract user from Authorization header if provided
        if authorization:
            token_data = await get_current_user_from_header(authorization)
            if token_data:
                user_id = token_data.user_id
                print(f"Analysis requested by user: {token_data.email}")
        
        progress_data[request_id] = "Initializing scan..."
        
        # Run parsing and git analysis concurrently
        ast_task = asyncio.create_task(
            run_in_threadpool(parse_code, req.repo_url, req.branch, request_id)
        )
        progress_data[request_id] = "Analysing git history..."
        git_metadata_task = asyncio.create_task(
            run_in_threadpool(get_repo_git_analysis, req.repo_url, req.branch, request_id)
        )
        
        progress_data[request_id] = "Putting the final pieces. Hope it was worth the wait (it probably wasn't)."
        ast, git_metadata = await asyncio.gather(ast_task, git_metadata_task)
        progress_data[request_id] = "done"

        # Save analysis to database if user is authenticated
        if user_id:
            try:
                # Check if repo analysis already exists
                repo_analysis = db.query(RepoAnalysis).filter(
                    RepoAnalysis.repo_url == req.repo_url,
                    RepoAnalysis.branch == req.branch
                ).first()
                
                if not repo_analysis:
                    # Create new repo analysis record
                    repo_analysis = RepoAnalysis(
                        repo_url=req.repo_url,
                        branch=req.branch,
                        repo_analysis=ast,
                        git_analysis=git_metadata
                    )
                    db.add(repo_analysis)
                    db.commit()
                    db.refresh(repo_analysis)
                else:
                    # Update existing record
                    repo_analysis.repo_analysis = ast
                    repo_analysis.git_analysis = git_metadata
                    db.commit()
                
                # Create user analysis history record
                analysis_history = UserAnalysisHistory(
                    user_id=user_id,
                    repo_analysis_id=repo_analysis.id
                )
                db.add(analysis_history)
                db.commit()
                
                print(f"Analysis saved to user history for user_id: {user_id}")
                
            except Exception as e:
                print(f"Warning: Could not save analysis to database: {e}")
                # Don't fail the request if database save fails
        
        return {
            "repo_analysis": ast,
            "git_analysis": git_metadata,
            "saved_to_history": user_id is not None
        }

    except Exception as e:
        traceback.print_exc()
        progress_data[request_id] = f"error: {str(e)}"
        return {"error": str(e)}

    finally:
        # Cleanup progress data after request completes
        if request_id in progress_data:
            del progress_data[request_id]



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
async def ask_route(req: AskRequest):
    """
    AI-powered code assistant endpoint with Redis-backed chat history.
    
    Features:
    - Maintains conversation context across requests via Redis
    - 1-hour TTL for chat sessions (auto-cleanup)
    - Optional history reset for starting fresh conversations
    
    Args:
        req: AskRequest with question, code, history_id, and reset flag
    
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
