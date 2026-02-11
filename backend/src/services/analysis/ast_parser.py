import os
from typing import Dict, List, Optional, Any
from tree_sitter import Language, Parser
import subprocess
import tempfile
import tree_sitter_java as tsjava
import tree_sitter_c as tsc
import tree_sitter_cpp as tscpp
import tree_sitter_javascript as tsjavascript
import tree_sitter_python as tspython
import tree_sitter_typescript as tstypescript
from src.config.language_node_maps import language_node_maps
from src.services.analysis.file_graph_generator import build_dependency_graph
from src.services.utilities.git_utils import get_file_git_info
from src.services.analysis.parse_utils import extract_import_data
from src.shared.progress import progress_data


LANGUAGE_LOADING_MESSAGES = {
    "cpp": "C++ detected — where one wrong pointer ruins your day 😅",
    "c": "C detected — manual memory management zone 🧠💥",
    "java": "Java detected. Hold tight, this might take a while ⏳",
    "python": "Python detected. Smooth ride incoming 🐍",
    "javascript": "JavaScript detected — semicolons are optional, bugs are not 😜",
    "typescript": "TypeScript detected — now with types and twice the compile time ⌛",
    "tsx": "TSX detected — React and TypeScript? Brave soul 👨‍🚀"
}


LANGUAGE_GRAMMARS = {
    "python": tspython.language(),
    "javascript": tsjavascript.language(),
    "typescript": tstypescript.language_typescript(),
    "tsx": tstypescript.language_tsx(),
    "java": tsjava.language(),
    "cpp": tscpp.language(),
    "c": tsc.language(),
}

LANGUAGE_FILE_EXTENSIONS = {
    "python": [".py"],
    "javascript": [".js", ".jsx"],
    "typescript": [".ts"],
    "tsx": [".tsx"],
    "java": [".java"],
    "cpp": [".cpp", ".hpp"],
    "c": [".c", ".h"],
}

parser_cache = {}

def get_parser(language):
    if language in parser_cache:
        return parser_cache[language]
    try:
        grammar_path = LANGUAGE_GRAMMARS[language]
        lang_obj = Language(grammar_path)
        parser = Parser(lang_obj)
        parser_cache[language] = parser
        return parser
    except KeyError:
        raise ValueError(f"Unsupported language: {language}")
    except TypeError:
        raise ValueError(f"Invalid grammar path for {language}: {grammar_path}")



def calculate_complexity(node):
    """Calculate simplified cyclomatic complexity"""
    complexity = 1
    stack = [node]
    while stack:
        current = stack.pop()
        if current.type in ("if_statement", "for_statement", "while_statement"):
            complexity += 1
        stack.extend(current.children)
    return complexity

def detect_file_language(filename: str):
    for language, extensions in LANGUAGE_FILE_EXTENSIONS.items():
        if any(filename.endswith(ext) for ext in extensions):
            return language
    return None



def extract_methods(node):
    """Helper function to extract methods from a class node."""
    methods = []
    for child in node.children:
        if child.type in ["function_definition", "method_definition"]:
            method_name = child.child_by_field_name("name").text.decode()
            methods.append(method_name)
    return methods

def extract_callee_name(call_node):
    """
    Given a call_expression node, extract a readable callee name.
    """
    callee_node = call_node.child_by_field_name("function") or call_node.child_by_field_name("callee") or call_node.children[0]

    if callee_node is None:
        callee_node = call_node.children[0]

    return get_node_name(callee_node)

def get_node_name(node):
    """
    Recursively convert a node to a string representing the callee name.
    Supports identifiers, member expressions, etc.
    """
    if node.type == "identifier":
        return node.text.decode()

    if node.type == "member_expression":
        object_node = node.child_by_field_name("object")
        property_node = node.child_by_field_name("property")
        object_name = get_node_name(object_node) if object_node else ""
        property_name = get_node_name(property_node) if property_node else ""
        if object_name and property_name:
            return f"{object_name}.{property_name}"
        return object_name or property_name

    if node.type == "call_expression":
        return extract_callee_name(node)

    return node.text.decode()

def parse_code(local_repo_path: str, repo_url: str, branch: str, request_id: str):
    """
    Parse code from a locally cloned repository.
    
    Args:
        local_repo_path: Path to the locally cloned repository
        repo_url: GitHub repository URL (used only for git info queries)
        branch: Branch name
        request_id: Request ID for progress tracking
    
    Returns:
        Dictionary with AST and dependency graph
    """
    print("Parsing repo ...")
    progress_data[request_id] = "Collecting source code..."
    print(f"[DEBUG] parse_code starting for request_id: {request_id}")
    
    result = {}
    repo_path = local_repo_path
    
    # Get all source code files from local repository
    source_files = []
    for root, dirs, files in os.walk(repo_path):
        # Skip hidden directories and common non-source directories
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', '.git']]
        
        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, repo_path)
            language = detect_file_language(file)
            
            # Only process files with supported languages
            if language and language in LANGUAGE_GRAMMARS:
                source_files.append((file_path, relative_path, language))
    
    print(f"Found {len(source_files)} source files to parse")
    progress_data[request_id] = f"Found {len(source_files)} source files to parse"
    
    for idx, (file_path, relative_path, language) in enumerate(source_files, 1):
        norm_path = os.path.normpath(relative_path)
        progress_msg = f"[{idx}/{len(source_files)}] Analyzing {norm_path} ({language})..."
        progress_data[request_id] = progress_msg
        print(f"[DEBUG] {progress_msg}")
        
        parser = get_parser(language)
        if not parser:
            continue
        
        try:
            # Read file content from local filesystem
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                code = f.read()
            
            tree = parser.parse(code.encode('utf-8'))
            
            extracted_info = {
                "language": language,
                "imports": [],
                "classes": [],
                "functions": [],
                "git_info": {
                    "commit_count": 0,
                    "last_modified": None,
                    "recent_commits": [],
                },
                "calls": []
            }
            
            # Note: get_file_git_info now uses local git commands instead of API calls
            try:
                extracted_info["git_info"] = get_file_git_info(repo_path, relative_path, branch)
            except Exception as e:
                print(f"Warning: Could not get git info for {relative_path}: {e}")
            
            current_function = None
            
            def traverse(node):
                nonlocal current_function
                node_text = code[node.start_byte:node.end_byte]
                start_line = node.start_point[0] + 1  # 1-based line numbering
                node_type = node.type
                node_map = language_node_maps.get(language, {})
                
                # Handle import extraction
                if node_type in node_map.get('imports', []):
                    import_info = extract_import_data(node, code, language, relative_path)
                    extracted_info["imports"].append(import_info)
                
                # Handle class extraction
                if node_type in node_map.get('classes', []):
                    class_info = {
                        "name": node.child_by_field_name("name").text.decode(),
                        "content": node_text,
                        "start_line": start_line,
                        "methods": extract_methods(node),
                        "metadata": {
                            "type": node_type,
                            "complexity": calculate_complexity(node)
                        }
                    }
                    extracted_info["classes"].append(class_info)
                
                # Handle functions
                if node_type in node_map.get('functions', []):
                    name_node = node.child_by_field_name("name")
                    name = name_node.text.decode() if name_node else f"<anonymous>:Line-{start_line}"
                    current_function = name
                    func_info = {
                        "name": name,
                        "content": node_text,
                        "start_line": start_line,
                        "metadata": {
                            "type": node_type,
                            "complexity": calculate_complexity(node)
                        }
                    }
                    extracted_info["functions"].append(func_info)
                
                # Handle calls
                if node_type in node_map.get('calls', []):
                    caller = current_function
                    callee_name = extract_callee_name(node)
                    extracted_info["calls"].append({
                        "caller": caller,
                        "callee": callee_name,
                        "location": {
                            "line": node.start_point[0] + 1,
                            "column": node.start_point[1] + 1
                        }
                    })
                
                for child in node.children:
                    traverse(child)
            
            traverse(tree.root_node)
            result[norm_path] = extracted_info
            
        except Exception as e:
            print(f"Error processing {norm_path}: {e}")
    
    print("Repo parsed successfully...")
    progress_data[request_id] = "Building architecture map..."
    graph = build_dependency_graph(result)
    
    # Debug logging
    print(f"[DEBUG] parse_code returning: ast with {len(result)} files")
    print(f"[DEBUG] First few file keys: {list(result.keys())[:5]}")
    
    return {
        "ast": result,
        "dependency_graph": graph
    }