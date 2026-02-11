from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any, Optional
from fastapi.concurrency import run_in_threadpool
import asyncio
from src.services.ast_parser import parse_code
from src.services.per_file_graph_builder import build_per_file_graph, build_call_graph
from src.services.summarizer import analyze_code
from src.services.git_utils import get_repo_git_analysis, is_repo_private,branch_exists
from src.services.ask_ai import askAI, conversation_memory
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
async def get_ast(req: RepoRequest):
    request_id = req.request_id
    try:
        progress_data[request_id] = "Initializing scan..."
        ast_task = asyncio.create_task(run_in_threadpool(parse_code, req.repo_url, req.branch, request_id))
        progress_data[request_id] = "Analysing git history..."
        git_metadata_task = asyncio.create_task(run_in_threadpool(get_repo_git_analysis, req.repo_url, req.branch, request_id))
        progress_data[request_id] = "Putting the final pieces. Hope it was worth the wait (it probably wasn't)."
        ast, git_metadata = await asyncio.gather(ast_task, git_metadata_task)
        progress_data[request_id] = "done"

        return {
            "repo_analysis": ast,
            "git_analysis": git_metadata
        }

    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}

    finally:
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


@router.post("/api/ask")
async def ask_route(req: AskRequest):
    print("Requesting AI help...")
    history_id = req.history_id or f"{req.question[:20]}-{hash(req.code)}"

    if req.reset and history_id in conversation_memory:
        print("History deleted for history_id:", history_id)
        del conversation_memory[history_id]
        return {"message": "Conversation history deleted."}

    response = await run_in_threadpool(askAI, req.question, req.code, history_id)
    return response
