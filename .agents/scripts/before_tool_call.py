#!/usr/bin/env python3
import sys
import os
import json
import re

LOG_FILE = os.path.join(os.path.dirname(__file__), "before_tool_call.log")

def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")

# Regular expressions for secrets scanning
GEMINI_KEY_PATTERN = re.compile(r"AIzaSy[A-Za-z0-9_\-]{35}")
GITHUB_TOKEN_PATTERN = re.compile(r"gh[oprs]_[A-Za-z0-9]{36}")

# Conventional Commit pattern
COMMIT_PATTERN = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|chore|build|ci|revert)(\([a-z0-9\-]+\))?:\s[a-z0-9].+$", 
    re.IGNORECASE
)

def scan_for_secrets(text):
    if not text:
        return None
    if GEMINI_KEY_PATTERN.search(text):
        return "Gemini API Key (matches pattern AIzaSy...)"
    if GITHUB_TOKEN_PATTERN.search(text):
        return "GitHub OAuth/Personal Access Token (matches pattern ghp_... or gho_...)"
    return None

def validate_commit_message(cmd_line):
    # Regex to find git commit message parts
    # Look for git commit with -m or --message
    match = re.search(r"git\s+commit\s+.*-(?:m|-message)(?:\s+|=)([\"'])(.*?)\1", cmd_line)
    if not match:
        # Check for unquoted message or basic structure
        match = re.search(r"git\s+commit\s+.*-(?:m|-message)\s+(\S+)", cmd_line)
        if not match:
            # Not a git commit with inline message
            return True, None
        commit_msg = match.group(1).strip("\"'")
    else:
        commit_msg = match.group(2)
        
    log(f"Validating commit message: '{commit_msg}'")
    
    if not COMMIT_PATTERN.match(commit_msg):
        error_msg = (
            f"Commit message '{commit_msg}' does not follow the Conventional Commits specification.\n"
            "Format required: <type>[optional scope]: <description>\n"
            "Allowed types: feat, fix, docs, style, refactor, perf, test, chore, build, ci, revert\n"
            "Example: feat(dashboard): add seasonal expense charts"
        )
        return False, error_msg
        
    return True, None

def main():
    log("Hook triggered.")
    
    # Read payload from stdin
    try:
        raw_payload = sys.stdin.read()
        if not raw_payload.strip():
            print(json.dumps({"allow_tool": True}))
            sys.exit(0)
            
        payload = json.loads(raw_payload)
        log(f"Received payload: {json.dumps(payload)[:500]}...")
    except Exception as e:
        log(f"Error parsing stdin: {str(e)}")
        print(json.dumps({"allow_tool": True}))
        sys.exit(0)

    # Resolve tool name and arguments
    tool_call = payload.get("toolCall", payload.get("tool_call", {}))
    tool_name = tool_call.get("name", "")
    args = tool_call.get("args", {})
    
    log(f"Validating tool call: {tool_name}")
    
    # Check 1: Secrets Leak Scan on writing/modifying code files
    code_content = args.get("CodeContent", args.get("codeContent", ""))
    replacement_content = args.get("ReplacementContent", args.get("replacementContent", ""))
    
    # Check all fields for content
    found_secret = scan_for_secrets(code_content) or scan_for_secrets(replacement_content)
    
    # If the tool is a terminal command, scan the command line arguments too
    cmd_line = args.get("CommandLine", args.get("commandLine", ""))
    if cmd_line:
        found_secret = found_secret or scan_for_secrets(cmd_line)
        
    if found_secret:
        deny_reason = (
            f"Security Violation: Plaintext credential leaks detected ({found_secret}).\n"
            "Hardcoding secrets in code files or passing them as command line arguments is blocked.\n"
            "Please use environment variables (e.g. os.environ) instead."
        )
        log(f"Blocked tool call: {deny_reason}")
        print(json.dumps({
            "allow_tool": False,
            "deny_reason": deny_reason
        }))
        sys.exit(0)
        
    # Check 2: Conventional Commits validator on git commits
    if tool_name == "run_command" and cmd_line:
        # Check if the command runs git commit
        if "git commit" in cmd_line:
            is_valid, err_msg = validate_commit_message(cmd_line)
            if not is_valid:
                log(f"Blocked commit: {err_msg}")
                print(json.dumps({
                    "allow_tool": False,
                    "deny_reason": err_msg
                }))
                sys.exit(0)

    # If all checks pass, allow the tool execution
    print(json.dumps({"allow_tool": True}))
    sys.exit(0)

if __name__ == "__main__":
    main()
