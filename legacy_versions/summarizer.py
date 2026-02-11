import os
import json
from typing import Dict
from dotenv import load_dotenv
from pathlib import Path
from src.services.git_utils import extract_owner_repo, download_file
import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError
import re
from src.services.ast_parser import detect_file_language

# Load .env from root directory
env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")  # Use correct key name
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in environment variables.")

genai.configure(api_key=GOOGLE_API_KEY)

def get_code_from_file(repo_url: str, branch: str, relative_path: str) -> str:
    owner, repo = extract_owner_repo(repo_url)
    github_path = relative_path.replace("\\", "/")
    code = download_file(owner, repo, github_path, branch)
    return code

def analyze_code(repo_url: str, branch: str, relative_path: str) -> Dict[str, str]:
    language = detect_file_language(relative_path)
    code = get_code_from_file(repo_url, branch, relative_path)

    # Initialize model
    model = genai.GenerativeModel("gemini-1.5-flash")  # Or gemini-1.5-pro / gemini-2.0 if available

    prompt = (
        "You are a code analysis assistant. Given a single code file, return a JSON object with two fields: \"summary\" and \"tutorial\".\n\n"
        "- \"summary\" should be a detailed explanation of what this file/component/page does. Focus only on this file — do not refer to any other files or the whole repo.\n\n"
        "- \"tutorial\" should be an array of step-by-step explanations of how the code works. Each step must be a JSON object with:\n"
        "  - \"step\": a beginner-friendly explanation of what the code is doing in that part.\n"
        "  - \"lines\": an array of line numbers (integers) or a range of line numbers (as [start, end]).\n"
        "If a step refers to one line, use a single number (e.g., 5). If it spans multiple lines, use a two-element array (e.g., [10, 14]).\n\n"
        "Return only valid JSON with this format:\n"
        "{\n"
        "  \"summary\": \"...\",\n"
        "  \"tutorial\": [\n"
        "    { \"step\": \"This part imports dependencies.\", \"lines\": [1, 3] },\n"
        "    { \"step\": \"Defines the main component and initializes state.\", \"lines\": [5, 12] },\n"
        "    { \"step\": \"Handles side effects with useEffect.\", \"lines\": [14, 25] },\n"
        "    ...\n"
        "  ]\n"
        "}\n\n"
        f"Here is the code:\n\n{code}"
    )

    try:
        response = model.generate_content(prompt)
        response_text = response.text

        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", response_text.strip(), flags=re.IGNORECASE)
        parsed = json.loads(cleaned)
        parsed["code"] = code
        parsed["language"] = language
        return parsed
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON returned by Gemini: {response_text}")
    except GoogleAPIError as e:
        print(f"Gemini error: {str(e)}")
        return {
            "error": "Gemini AI service is currently unavailable. Please try again later.",
            "code": code,
            "language": language
        }
