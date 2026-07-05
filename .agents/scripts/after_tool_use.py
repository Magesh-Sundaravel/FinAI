#!/usr/bin/env python3
import sys
import os
import json
import subprocess

LOG_FILE = os.path.join(os.path.dirname(__file__), "after_tool_use.log")

def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")

def main():
    log("Hook triggered.")
    
    # Read payload from stdin
    try:
        raw_payload = sys.stdin.read()
        if not raw_payload.strip():
            log("No stdin payload found.")
            print(json.dumps({"allow_tool": True}))
            sys.exit(0)
            
        payload = json.loads(raw_payload)
        log(f"Received payload: {json.dumps(payload)[:500]}...")
    except Exception as e:
        log(f"Error parsing stdin: {str(e)}")
        print(json.dumps({"allow_tool": True}))
        sys.exit(0)

    # Resolve tool call name and arguments
    tool_call = payload.get("toolCall", payload.get("tool_call", {}))
    tool_name = tool_call.get("name", "")
    args = tool_call.get("args", {})
    
    log(f"Tool executed: {tool_name}")
    
    # Check if a file was written or modified
    target_file = args.get("TargetFile", args.get("targetFile", ""))
    
    # Check if the tool is one of the file-modifying tools
    is_write_tool = tool_name in ["write_to_file", "replace_file_content", "multi_replace_file_content"]
    
    if is_write_tool and target_file:
        log(f"File modified: {target_file}")
        
        # Verify the file exists and is a Python file
        if os.path.exists(target_file) and target_file.endswith(".py"):
            log("Target is a Python file. Running linter and formatters...")
            
            # Find the backend directory root to run commands
            # We look for pyproject.toml in parent directories
            cwd = os.path.dirname(target_file)
            while cwd and cwd != "/":
                if os.path.exists(os.path.join(cwd, "pyproject.toml")):
                    break
                cwd = os.path.dirname(cwd)
                
            if not cwd or cwd == "/":
                cwd = "/home/magesh/Magesh/AI/Google/FinAI/backend" # default fallback
                
            log(f"Running checks in workspace: {cwd}")
            
            # Run ruff format
            try:
                log(f"Running: uv run ruff format {target_file}")
                fmt_res = subprocess.run(
                    ["uv", "run", "ruff", "format", target_file],
                    cwd=cwd,
                    capture_output=True,
                    text=True
                )
                log(f"Format result (stdout): {fmt_res.stdout}")
                if fmt_res.stderr:
                    log(f"Format result (stderr): {fmt_res.stderr}")
            except Exception as e:
                log(f"Failed to format: {str(e)}")
                
            # Run ruff check --fix
            try:
                log(f"Running: uv run ruff check --fix {target_file}")
                chk_res = subprocess.run(
                    ["uv", "run", "ruff", "check", "--fix", target_file],
                    cwd=cwd,
                    capture_output=True,
                    text=True
                )
                log(f"Check result (stdout): {chk_res.stdout}")
                if chk_res.stderr:
                    log(f"Check result (stderr): {chk_res.stderr}")
            except Exception as e:
                log(f"Failed to check: {str(e)}")
                
            # Run mypy typechecking
            try:
                log(f"Running: uv run mypy {target_file}")
                mypy_res = subprocess.run(
                    ["uv", "run", "mypy", target_file],
                    cwd=cwd,
                    capture_output=True,
                    text=True
                )
                log(f"Mypy result (stdout): {mypy_res.stdout}")
                if mypy_res.stderr:
                    log(f"Mypy result (stderr): {mypy_res.stderr}")
            except Exception as e:
                log(f"Failed to typecheck: {str(e)}")

    # Antigravity hook stdout contract expectation
    print(json.dumps({"allow_tool": True}))
    sys.exit(0)

if __name__ == "__main__":
    main()
