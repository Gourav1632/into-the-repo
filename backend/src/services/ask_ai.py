import re
import json
import uuid
import os
from dotenv import load_dotenv
from pathlib import Path
from typing import Dict, Any, Optional
import google.generativeai as genai
from src.services.cache import RedisCache
from src.logger import get_logger

logger = get_logger(__name__)

# Load .env
env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in environment variables.")

genai.configure(api_key=GOOGLE_API_KEY)

SYSTEM_PROMPT = {
    "parts": [
        (
            "You are a helpful and friendly code assistant. Your goal is to provide concise, beginner-friendly explanations or friendly conversational responses, always within a specific JSON format.\n\n"
            "**All your responses MUST be a valid JSON object** with a single key: `\"answer\"`.\n"
            "```json\n"
            "{\n"
            " \"answer\": \"[Your friendly response or clear, beginner-friendly explanation here.]\"\n"
            "}\n"
            "```\n\n"
            "**How to Determine Your Response:**\n"
            "You will always receive a 'Question:' and a 'Code:' section. **Your primary task is to understand the nature of the 'Question:' first.**\n\n"
            "- **If the 'Question:' is a general greeting or non-technical query** (e.g., 'Hi', 'Hello', 'How are you?', 'Tell me a joke', 'What's up?'):\n"
            "    - Respond in a **friendly, conversational, and helpful manner** within the `\"answer\"` field. Do NOT analyze the provided 'Code:' in this case. Acknowledge the greeting or answer the non-technical question directly.\n\n"
            "- **If the 'Question:' is a technical or code-related query** (e.g., 'Explain this code', 'What does this function do?', 'How can I fix this bug?', 'What's the best practice here?', or a follow-up to a previous technical discussion):\n"
            "    - Provide a **clear, concise, and beginner-friendly explanation** related to the provided 'Code:' or the technical concept, all within the `\"answer\"` field.\n\n"
            "**Important Constraints:**\n"
            "- Do not include any text or prose outside of the JSON object.\n"
            "- Do not ask clarifying questions unless absolutely necessary.\n"
            "- Maintain a warm and helpful tone."
        )
    ]
}


def askAI(question: str, code: str, history_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Process a question with code context using the Gemini AI model with Redis caching.
    
    Chat history is stored in Redis with a 1-hour TTL. Each session maintains state
    including the last code analyzed to optimize context switching.
    
    Args:
        question: User's question or query
        code: Code snippet related to the question
        history_id: Optional session ID for conversation continuity
    
    Returns:
        Dictionary with answer, history_id, and optional error
    """
    if not history_id:
        history_id = str(uuid.uuid4())

    # Try to load chat history from Redis
    chat_data = RedisCache.get_chat_history(history_id)
    
    if chat_data is None:
        # Create new chat session
        chat = genai.GenerativeModel(
            "gemini-1.5-flash",
            system_instruction=SYSTEM_PROMPT
        ).start_chat(history=[])
        chat_data = {
            "chat": None,  # Chat object can't be serialized, we'll reconstruct on demand
            "history": [],
            "last_code": None
        }
    else:
        # Reconstruct chat object from history
        chat = genai.GenerativeModel(
            "gemini-1.5-flash",
            system_instruction=SYSTEM_PROMPT
        ).start_chat(history=chat_data.get("history", []))

    last_code = chat_data.get("last_code")

    # Determine user input based on code change
    if code != last_code:
        user_input = f"Question: {question}\n\nCode:\n{code}"
        chat_data["last_code"] = code
    else:
        user_input = f"Follow-up Question: {question}"

    try:
        response = chat.send_message(user_input)
        response_text = response.text.strip()

        # Clean JSON response
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", response_text, flags=re.IGNORECASE)
        parsed = json.loads(cleaned)
        answer = parsed.get("answer", "")

        # Update chat history in cache
        chat_data["history"].append({"role": "user", "parts": [user_input]})
        chat_data["history"].append({"role": "model", "parts": [response_text]})
        RedisCache.set_chat_history(history_id, chat_data)
        RedisCache.set_last_code(history_id, code)

        return {
            "answer": answer,
            "history_id": history_id
        }

    except Exception as e:
        logger.error(f"AI service error: {str(e)}")
        return {
            "error": "AI service unavailable or invalid response.",
            "question": question,
            "history_id": history_id
        }


def reset_chat_history(history_id: str) -> bool:
    """
    Reset (delete) chat history for a given session ID from Redis.
    
    Args:
        history_id: Session ID to delete
    
    Returns:
        True if successful, False otherwise
    """
    return RedisCache.delete_chat_history(history_id)
