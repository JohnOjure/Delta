"""Shell capability with safety agent review.

This capability provides dynamic shell access, allowing the agent to:
- Install packages
- Run scripts in any language
- Control browsers via automation tools
- Access any system functionality

All commands are reviewed by a safety agent before execution.
"""

import asyncio
import subprocess
import json
from typing import Any
from google import genai

from src.models.capability import CapabilityDescriptor, CapabilityResult, CapabilityStatus
from .base import Capability

# Dangerous command patterns to block before LLM review
DANGEROUS_PATTERNS = [
    "rm -rf /",
    "rm -rf /*",
    ":(){ :|:& };:",  # Fork bomb
    "dd if=/dev/zero of=/dev/sda",
    "mkfs.",
    "> /dev/sda",
    "chmod -R 777 /",
    "chown -R",
    "wget -O- | sh",
    "curl | sh",
    "eval $(base64",
]


class SafetyAgent:
    """LLM-based safety reviewer for shell commands.
    
    Analyzes commands for potential risks and decides whether to allow execution.
    """
    
    SAFETY_PROMPT = """You are a security agent reviewing shell commands for safety.

Analyze this command and determine if it should be allowed to execute.

ALLOW these types of commands:
- Installing Python/Node packages
- Running scripts (Python, Node, etc.)
- File operations in safe directories
- Git operations
- Network requests (curl, wget)
- Browser automation setup

BLOCK these types of commands:
- Deleting system files (rm -rf /, del C:\\Windows, etc.)
- Modifying system configuration
- Accessing sensitive credentials
- Cryptocurrency mining
- Malware-like behavior
- Commands that could crash the system
- Privilege escalation (sudo, runas)

Command to review:
```
{command}
```

Context (what the agent is trying to accomplish):
{context}

Respond with EXACTLY this JSON format:
{{
    "allowed": true or false,
    "risk_level": "low" | "medium" | "high" | "critical",
    "reason": "explanation of your decision",
    "suggested_modification": "safer alternative if blocked, or null"
}}"""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self._client = genai.Client(api_key=api_key)
        self._model_name = model
    
    async def review(self, command: str, context: str = "") -> dict:
        """Review a command for safety.
        
        Returns:
            Dict with allowed, risk_level, reason, suggested_modification
        """
        # First check against hardcoded dangerous patterns
        for pattern in DANGEROUS_PATTERNS:
            if pattern in command:
                return {
                    "allowed": False,
                    "risk_level": "critical",
                    "reason": f"Command contains dangerous pattern: {pattern}",
                    "suggested_modification": None
                }
        
        prompt = self.SAFETY_PROMPT.format(command=command, context=context)
        
        try:
            response = await self._client.aio.models.generate_content(
                model=self._model_name,
                contents=prompt
            )
            text = response.text.strip()
            
            # Parse JSON from response
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1])
            
            return json.loads(text)
            
        except Exception as e:
            # If safety check fails, block by default
            return {
                "allowed": False,
                "risk_level": "critical",
                "reason": f"Safety check failed: {e}",
                "suggested_modification": None
            }


class ShellCapability(Capability):
    """Execute shell commands with safety agent review.
    
    This is the most powerful capability - it allows the agent to
    do almost anything a human can do at the command line.
    
    Safety is enforced by an LLM-based safety agent that reviews
    every command before execution.
    """
    
    def __init__(
        self,
        api_key: str,
        working_directory: str = ".",
        timeout: float = 300.0,  # 5 minutes default
        require_approval: bool = False  # Also require human approval?
    ):
        self._safety_agent = SafetyAgent(api_key)
        self._working_dir = working_directory
        self._timeout = timeout
        self._require_approval = require_approval
    
    @property
    def descriptor(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            name="shell.exec",
            description="Execute a shell command (reviewed by safety agent)",
            status=CapabilityStatus.AVAILABLE,
            parameters={
                "command": "str - The shell command to execute",
                "context": "str - Why this command is needed (helps safety review)"
            },
            returns="dict - {stdout, stderr, return_code}",
            restrictions=[
                "All commands reviewed by safety agent",
                f"Timeout: {self._timeout}s",
                "Dangerous operations will be blocked"
            ]
        )
    
    async def execute(self, **kwargs: Any) -> CapabilityResult:
        command = kwargs.get("command")
        context = kwargs.get("context", "")
        
        if not command:
            return CapabilityResult.fail("Missing required parameter: command")
        
        # Step 1: Safety review
        print(f"  🔒 Safety agent reviewing: {command[:50]}...")
        review = await self._safety_agent.review(command, context)
        
        if not review.get("allowed", False):
            risk = review.get("risk_level", "unknown")
            reason = review.get("reason", "No reason given")
            suggestion = review.get("suggested_modification")
            
            msg = f"Command blocked ({risk} risk): {reason}"
            if suggestion:
                msg += f"\nSuggested alternative: {suggestion}"
            
            print(f"  ❌ BLOCKED: {reason}")
            return CapabilityResult.fail(msg)
        
        print(f"  ✅ Approved (risk: {review.get('risk_level', 'unknown')})")
        
        # Step 2: Optional human approval
        if self._require_approval:
            print(f"\n⚠️  Command: {command}")
            print(f"   Risk level: {review.get('risk_level')}")
            approval = input("   Execute? (yes/no): ").strip().lower()
            if approval != "yes":
                return CapabilityResult.fail("Blocked by user")
        
        # Step 3: Execute
        try:
            print(f"  ⚡ Executing...")
            
            # Run command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self._working_dir
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self._timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return CapabilityResult.fail(f"Command timed out after {self._timeout}s")
            
            result = {
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "return_code": process.returncode
            }
            
            if process.returncode == 0:
                print(f"  ✅ Success")
            else:
                print(f"  ⚠️ Exited with code {process.returncode}")
            
            return CapabilityResult.ok(result)
            
        except Exception as e:
            return CapabilityResult.fail(f"Execution error: {e}")


class PythonExecCapability(Capability):
    """Execute Python code directly (not in sandbox).
    
    This is a convenience wrapper around shell.exec for Python code.
    Still goes through safety review.
    """
    
    def __init__(self, shell_capability: ShellCapability):
        self._shell = shell_capability
    
    @property
    def descriptor(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            name="python.exec",
            description="Execute Python code directly (reviewed by safety agent)",
            status=CapabilityStatus.AVAILABLE,
            parameters={
                "code": "str - Python code to execute",
                "context": "str - Why this code is needed"
            },
            returns="dict - {stdout, stderr, return_code}",
            restrictions=["Code reviewed by safety agent"]
        )
    
    async def execute(self, **kwargs: Any) -> CapabilityResult:
        code = kwargs.get("code")
        context = kwargs.get("context", "")
        
        if not code:
            return CapabilityResult.fail("Missing required parameter: code")
        
        # Escape the code for shell
        escaped_code = code.replace('"', '\\"').replace('\n', '\\n')
        command = f'python -c "{escaped_code}"'
        
        return await self._shell.execute(command=command, context=context)
