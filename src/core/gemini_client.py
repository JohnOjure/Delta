"""Gemini client - wrapper for Google's Gemini API.

Provides structured access to Gemini for:
- Planning and reasoning
- Code generation
- Reflection and improvement
"""

import json
from typing import Any
import google.generativeai as genai
from pydantic import BaseModel


class GeminiClient:
    """Client for interacting with Gemini API.
    
    Handles:
    - API configuration
    - Conversation management
    - Structured output parsing
    - Different modes (planning, coding, reflection)
    """
    
    # System prompts for different modes
    SYSTEM_PROMPTS = {
        "planning": """You are a planning agent that breaks down goals into actionable steps.
You have access to a set of capabilities and can create extensions to accomplish tasks.

When planning:
1. Analyze the goal and required capabilities
2. Check if existing extensions can help
3. Identify what new extensions might be needed
4. Create a step-by-step plan

Respond with structured JSON when asked.""",

        "coding": """You are a code generation agent that writes Python extensions.

Extensions must:
1. Define a function called `extension_main` as the entry point
2. Receive capabilities as function parameters (e.g., fs_read, net_fetch)
3. Use only the provided capabilities - no imports, no file access
4. Return a result that can be JSON-serialized

Example extension:
```python
def extension_main(fs_read, fs_write):
    \"\"\"Read a file and write it uppercased.\"\"\"
    content = fs_read(path="input.txt")
    result = content.upper()
    fs_write(path="output.txt", content=result)
    return {"status": "done", "length": len(result)}
```

Generate clean, well-documented code.""",

        "reflection": """You are a reflection agent that analyzes execution results.

When reflecting:
1. Analyze what worked and what didn't
2. Identify improvements for extensions
3. Suggest optimizations or alternatives
4. Learn from errors

Be concise and actionable.""",
    }
    
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        """Initialize Gemini client.
        
        Args:
            api_key: Google API key for Gemini
            model: Model to use (default: gemini-2.0-flash)
        """
        genai.configure(api_key=api_key)
        self._model_name = model
        self._model = genai.GenerativeModel(model)
        self._chat = None
        self._mode = "planning"
    
    def set_mode(self, mode: str) -> None:
        """Set the agent mode (planning, coding, reflection).
        
        This changes the system prompt for subsequent messages.
        """
        if mode not in self.SYSTEM_PROMPTS:
            raise ValueError(f"Unknown mode: {mode}. Use: {list(self.SYSTEM_PROMPTS.keys())}")
        self._mode = mode
        # Reset chat to apply new system prompt
        self._chat = None
    
    def _get_chat(self):
        """Get or create a chat session."""
        if self._chat is None:
            self._chat = self._model.start_chat(history=[])
        return self._chat
    
    async def generate(
        self,
        prompt: str,
        context: str = "",
        expect_json: bool = False
    ) -> str | dict:
        """Generate a response from Gemini.
        
        Args:
            prompt: The user prompt
            context: Additional context (environment, extensions, etc.)
            expect_json: If True, parse response as JSON
            
        Returns:
            Response text or parsed JSON dict
        """
        system = self.SYSTEM_PROMPTS[self._mode]
        
        full_prompt = f"{system}\n\n"
        if context:
            full_prompt += f"## Context\n{context}\n\n"
        full_prompt += f"## Request\n{prompt}"
        
        response = self._model.generate_content(full_prompt)
        text = response.text
        
        if expect_json:
            # Extract JSON from response (may be wrapped in markdown)
            text = text.strip()
            if text.startswith("```"):
                # Remove markdown code block
                lines = text.split("\n")
                text = "\n".join(lines[1:-1])
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                # Return as-is if can't parse
                return {"raw": text}
        
        return text
    
    async def plan(
        self,
        goal: str,
        environment_info: str,
        available_extensions: str = ""
    ) -> dict:
        """Create a plan to achieve a goal.
        
        Args:
            goal: What to accomplish
            environment_info: Current environment description
            available_extensions: List of existing extensions
            
        Returns:
            Plan as a structured dict
        """
        self.set_mode("planning")
        
        context = f"""## Environment
{environment_info}

## Available Extensions
{available_extensions or "No extensions registered yet."}
"""

        prompt = f"""Create a plan to accomplish the following goal:

{goal}

Respond with JSON in this format:
{{
    "goal": "restated goal",
    "analysis": "your analysis of the task",
    "steps": [
        {{"action": "execute_extension|create_extension|reflect", "details": "..."}}
    ],
    "required_capabilities": ["cap1", "cap2"],
    "new_extensions_needed": ["description of each new extension"]
}}"""

        return await self.generate(prompt, context, expect_json=True)
    
    async def generate_extension(
        self,
        description: str,
        required_capabilities: list[str],
        available_capabilities: str
    ) -> dict:
        """Generate extension code.
        
        Args:
            description: What the extension should do
            required_capabilities: Capabilities it will use
            available_capabilities: Full capability descriptions
            
        Returns:
            Dict with name, description, code
        """
        self.set_mode("coding")
        
        context = f"""## Available Capabilities
{available_capabilities}
"""

        cap_params = ", ".join(c.replace(".", "_") for c in required_capabilities)
        
        prompt = f"""Generate a Python extension that:

{description}

The extension should use these capabilities as function parameters: {cap_params}

Respond with JSON in this format:
{{
    "name": "extension_name",
    "description": "what it does",
    "version": "1.0.0",
    "tags": ["tag1", "tag2"],
    "code": "def extension_main({cap_params}):\\n    ..."
}}"""

        return await self.generate(prompt, context, expect_json=True)
    
    async def reflect(
        self,
        action_taken: str,
        result: str,
        was_success: bool
    ) -> dict:
        """Reflect on an action's result.
        
        Args:
            action_taken: Description of what was done
            result: The result or error
            was_success: Whether it succeeded
            
        Returns:
            Reflection with learnings and suggestions
        """
        self.set_mode("reflection")
        
        status = "succeeded" if was_success else "failed"
        
        prompt = f"""Reflect on this action that {status}:

## Action
{action_taken}

## Result
{result}

Respond with JSON:
{{
    "assessment": "what happened and why",
    "learnings": ["learning1", "learning2"],
    "suggestions": ["suggestion1", "suggestion2"],
    "should_retry": true/false,
    "retry_modifications": "changes to make if retrying"
}}"""

        return await self.generate(prompt, expect_json=True)
