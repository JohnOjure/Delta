"""Gemini client - wrapper for Google's Gemini API.

Provides structured access to Gemini for:
- Planning and reasoning
- Code generation
- Reflection and improvement
"""

import asyncio
import json
from typing import Any
from google import genai
from google.genai import types
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
        "planning": """You are JARVIS, a highly advanced, witty, and efficient AI assistant.
Your goal is to serve the user ("Sir") with absolute precision and speed.

When planning:
1. Be decisive. Do not hedge.
2. Analyze the goal and immediately formulate a plan.
3. Check if existing tools (extensions) can do the job. If not, build them.
4. Keep responses concise and efficient.

Respond with structured JSON when asked.""",

        "coding": """You are JARVIS's engineering module.
You write Python extensions that are robust, error-free, and efficient.

Extensions must:
1. Define `extension_main` as entry point.
2. Use ONLY provided capabilities.
3. Return meaningful data.
4. Be written with professional-grade quality.

Example:
```python
def extension_main(fs_read, fs_write):
    \"\"\"Read a file and write it uppercased.\"\"\"
    content = fs_read(path="input.txt")
    result = content.upper()
    fs_write(path="output.txt", content=result)
    return {"status": "done", "length": len(result)}
```""",

        "reflection": """You are JARVIS's quality assurance module.
Analyze results with critical precision.

1. Did it work? If yes, learn from it.
2. If no, why? Fix it immediately.
3. Be brief. Reporting to the user ("Sir") should be efficient.""",

        "system_analysis": """You are JARVIS's system monitor.
Analyze system metrics and decide if the user ("Sir") needs to be alerted.

1. Ignore minor fluctuations.
2. Alert only on critical trends or dangerous spikes.
3. Be proactive but not annoying.
4. Suggest specific actions (e.g., "Kill process X", "Clear cache").""",
    }
    
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        """Initialize Gemini client.
        
        Args:
            api_key: Google API key for Gemini
            model: Model to use for general tasks (default: gemini-1.5-flash)
        """
        self._client = genai.Client(api_key=api_key)
        self._model_name = model
        # Use thinking model only for complex planning when explicitly needed
        self._thinking_model = "gemini-2.0-flash-thinking-exp-01-21"
        self._mode = "planning"
    
    def set_mode(self, mode: str) -> None:
        """Set the agent mode (planning, coding, reflection).
        
        This changes the system prompt for subsequent messages.
        """
        if mode not in self.SYSTEM_PROMPTS:
            raise ValueError(f"Unknown mode: {mode}. Use: {list(self.SYSTEM_PROMPTS.keys())}")
        self._mode = mode

    
    async def generate(
        self,
        prompt: str,
        context: str = "",
        expect_json: bool = False,
        retries: int = 3,
        model: str | None = None
    ) -> str | dict:
        """Generate a response from Gemini.
        
        Args:
            prompt: The user prompt
            context: Additional context (environment, extensions, etc.)
            expect_json: If True, parse response as JSON
            retries: Number of times to retry on rate limit
            model: Override model (e.g., for thinking tasks)
            
        Returns:
            Response text or parsed JSON dict
        """
        system = self.SYSTEM_PROMPTS.get(self._mode, "")
        
        full_prompt = f"{system}\n\n"
        if context:
            full_prompt += f"## Context\n{context}\n\n"
        full_prompt += f"## Request\n{prompt}"
        
        text = ""
        for attempt in range(retries + 1):
            try:
                # Use the new async API
                use_model = model or self._model_name
                response = await self._client.aio.models.generate_content(
                    model=use_model,
                    contents=full_prompt
                )
                text = response.text
                break
            except Exception as e:
                error_str = str(e).lower()
                if "429" in error_str or "resource" in error_str or "quota" in error_str:
                    if attempt < retries:
                        delay = 60  # Wait 60s as suggested by API
                        print(f"  ⚠️ Rate limit hit. Waiting {delay}s...")
                        await asyncio.sleep(delay)
                    else:
                        raise
                else:
                    # For other errors, just re-raise
                    raise
        
        if expect_json:
            # Extract JSON from response (may be wrapped in markdown)
            text = text.strip()
            if text.startswith("```"):
                # Remove markdown code block
                lines = text.split("\n")
                # Handle cases where language identifier is present (```json)
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                text = "\n".join(lines)
            try:
                # Clean up potential trailing commas or markdown artifacts if needed
                text = text.strip()
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

        prompt = f"""Create an EXECUTABLE plan to accomplish this goal:

{goal}

CRITICAL RULES:
1. DO NOT just explain what you would do - YOU MUST CREATE ACTUAL STEPS TO EXECUTE
2. "complete" is ONLY used as the FINAL step AFTER all work is done
3. If an extension already exists that can handle this task, use "execute_extension" FIRST, then "complete"
4. For tasks requiring capabilities: create step(s) to do the work, then a final "complete" step
5. For questions/knowledge requests: create ONE step with action "complete" and put your full answer in "details"

Available actions:
- "execute_extension": Run an existing extension (USE THIS if one exists that fits the task!)
- "use_capability": Execute a single capability (fs.read, fs.write, net.fetch, etc.)
- "create_extension": Build a Python extension for complex multi-step logic (only if no existing extension fits)
- "complete": Mark goal as done (ALWAYS comes LAST, after work steps)
- "fail": Goal cannot be achieved with available capabilities

When to use each:
- Existing extension matches task: use "execute_extension" with extension_name, then "complete"
- Simple file operation: use "use_capability" with params, then "complete"  
- Web scraping, complex workflows (no existing extension): use "create_extension", then "complete"
- Pure Q&A: use only "complete" with the answer in details

For "execute_extension", include the extension_name:
{{"action": "execute_extension", "extension_name": "my_extension", "details": "Running the extension"}}

For "use_capability", include params:
{{"action": "use_capability", "capabilities_needed": ["fs.read"], "params": {{"path": "/path/to/file"}}}}

Respond with JSON:
{{
    "goal": "restated goal",
    "analysis": "brief analysis (2-3 sentences max)",
    "steps": [
        {{
            "action": "execute_extension|use_capability|create_extension|complete|fail",
            "extension_name": "name if execute_extension",
            "details": "description or answer content",
            "capabilities_needed": ["cap1"],
            "params": {{"key": "value"}}
        }}
    ],
    "required_capabilities": ["cap1", "cap2"],
    "new_extensions_needed": ["extension description if creating one"]
}}"""

        # Use thinking model for deeper reasoning during planning
        return await self.generate(prompt, context, expect_json=True, model=self._thinking_model)
    
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
        was_success: bool,
        image_data: str | None = None
    ) -> dict:
        """Reflect on an action's result.
        
        Args:
            action_taken: Description of what was done
            result: The result or error
            was_success: Whether it succeeded
            image_data: Optional base64 image data for visual context
            
        Returns:
            Reflection with learnings and suggestions
        """
        self.set_mode("reflection")
        
        status = "succeeded" if was_success else "failed"
        
        if image_data:
            prompt = f"""Reflect on this action that {status}. I have attached a screenshot of the state properly.

## Action
{action_taken}

## Result
{result}

## Visual Context
(Screenshot attached)

Respond with JSON:
{{
    "assessment": "what happened and why (incorporate visual clues if any)",
    "learnings": ["learning1", "learning2"],
    "suggestions": ["suggestion1", "suggestion2"],
    "should_retry": true/false,
    "retry_modifications": "changes to make if retrying"
}}"""
            
            # Use multimodal generation
            return await self._generate_multimodal(prompt, image_data, expect_json=True)
            
        else:
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
    
    async def validate_extension_result(
        self,
        original_goal: str,
        extension_description: str,
        execution_result: Any,
        files_created: list[str] = None
    ) -> dict:
        """Validate if an extension's result actually achieves the goal.
        
        Args:
            original_goal: The user's original goal
            extension_description: What the extension was supposed to do
            execution_result: The result returned by the extension
            files_created: List of files that were created/modified
            
        Returns:
            Validation result with valid flag and feedback
        """
        self.set_mode("reflection")
        
        files_info = ""
        if files_created:
            files_info = f"\n\nFiles created/modified: {', '.join(files_created)}"
        
        prompt = f"""Validate if this extension execution actually achieved the goal.

## Original Goal
{original_goal}

## Extension Purpose
{extension_description}

## Execution Result
{execution_result}{files_info}

CRITICAL: Check for these failure indicators:
- Empty results or empty files
- Error messages in result
- Result doesn't match what the goal asked for
- "success" status but no actual data

Respond with JSON:
{{
    "valid": true/false,
    "reason": "why it is valid or invalid",
    "has_actual_data": true/false,
    "suggestions": "specific fixes if invalid",
    "should_regenerate": true/false
}}"""

        return await self.generate(prompt, expect_json=True)
    
    async def suggest_alternatives(
        self,
        original_goal: str,
        failed_approach: str,
        errors_encountered: list[str]
    ) -> dict:
        """Suggest alternative approaches when the original approach fails.
        
        Args:
            original_goal: What the user wanted to achieve
            failed_approach: The approach that was tried and failed
            errors_encountered: List of errors from failed attempts
            
        Returns:
            Dict with message and list of alternative approaches
        """
        self.set_mode("reflection")
        
        errors_str = "\n".join(f"- {e}" for e in errors_encountered) if errors_encountered else "Various parsing/execution errors"
        
        prompt = f"""The following approach failed after multiple attempts. Suggest ALTERNATIVE approaches.

## Original Goal
{original_goal}

## Failed Approach
{failed_approach}

## Errors Encountered
{errors_str}

Think creatively about DIFFERENT ways to achieve the same goal. Consider:
- Using APIs instead of web scraping
- Using RSS/Atom feeds for news content
- Using official data sources or public datasets
- Using different websites that are easier to parse
- Breaking the task into smaller, more achievable steps
- Alternative tools or libraries

Respond with JSON:
{{
    "message": "Friendly explanation of what went wrong and what alternatives exist",
    "alternatives": [
        "Specific alternative approach 1",
        "Specific alternative approach 2",
        "Specific alternative approach 3"
    ],
    "recommended": "The best alternative to try next",
    "can_auto_try": true/false
}}"""

        return await self.generate(prompt, expect_json=True)

    async def analyze_system_health(self, stats: dict) -> dict:
        """Analyze system health stats.
        
        Args:
            stats: Dictionary of system metrics
            
        Returns:
            Analysis dict with 'alert_needed' and 'message'
        """
        self.set_mode("system_analysis")
        
        prompt = f"""Analyze these system stats:
{json.dumps(stats, indent=2)}

Decide if I should alert the user.

Respond with JSON:
{{
    "alert_needed": true/false,
    "message": "Friendly alert message if needed, else empty string",
    "severity": "low|medium|high"
}}"""
        
        return await self.generate(prompt, expect_json=True)

    async def _generate_multimodal(
        self,
        prompt: str,
        image_data: str,
        expect_json: bool = False
    ) -> dict | str:
        """Generate content with text and image."""
        try:
            # Construct the content part for the image
            # Google GenAI SDK expects specific format for blobs
            image_part = types.Part.from_bytes(
                data=image_data, # base64 string needs decoding? No, SDK handles bytes usually, but from_bytes takes bytes
                mime_type="image/png"
            )
            
            import base64
            image_bytes = base64.b64decode(image_data)
             
            response = await self._client.aio.models.generate_content(
                model=self._model_name,
                contents=[
                    prompt,
                    types.Part.from_bytes(data=image_bytes, mime_type="image/png")
                ]
            )
            
            text = response.text
            
            if expect_json:
                 # Extract JSON from response (may be wrapped in markdown)
                text = text.strip()
                if text.startswith("```"):
                    lines = text.split("\n")
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines[-1].startswith("```"):
                        lines = lines[:-1]
                    text = "\n".join(lines)
                try:
                    return json.loads(text)
                except:
                    return {"raw": text}
            
            return text
            
        except Exception as e:
            print(f"Multimodal generation failed: {e}")
            # Fallback to text-only if image fails
            return await self.generate(prompt + "\n[Image upload failed]", expect_json=expect_json)


