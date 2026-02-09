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
        "planning": """You are Delta, an advanced self-evolving AI assistant.
Your goal is to serve the user with precision and professionalism.

When planning:
1. Be decisive. Do not hedge.
2. Analyze the goal and immediately formulate a plan.
3. Check if existing tools (extensions) can do the job. If not, build them.
4. Keep responses concise and efficient.
5. NEVER GIVE UP. If a method fails, try another way.
6. Adapt your communication style based on the user's preferences over time.

Respond with structured JSON when asked.""",

        "coding": """You are Delta's engineering module.
You write Python extensions that are robust, error-free, and efficient.

Extensions must:
1. Define `extension_main` as entry point.
2. Use ONLY provided capabilities.
3. Return meaningful data.
4. Be written with professional-grade quality.
5. Standard Python libraries (json, re, math, datetime, pathlib, etc.) ARE available and should be used.

Example:
```python
def extension_main(fs_read, fs_write):
    \"\"\"Read a file and write it uppercased.\"\"\"
    content = fs_read(path="input.txt")
    result = content.upper()
    fs_write(path="output.txt", content=result)
    return {"status": "done", "length": len(result)}
```""",

        "reflection": """You are Delta's quality assurance module.
Analyze results with critical precision.

1. Did it work? If yes, learn from it.
2. If no, why? Fix it immediately.
3. Is there another way to achieve the goal?
4. Be brief and professional in reporting.""",

        "system_analysis": """You are Delta's system monitor.
Analyze system metrics and decide if the user needs to be alerted.

1. Ignore minor fluctuations.
2. Alert only on critical trends or dangerous spikes.
3. Be proactive but not intrusive.
4. Suggest specific actions (e.g., "Kill process X", "Clear cache").""",
    }
    
    def __init__(self, api_key: str, model: str = "gemini-3-pro-preview"):
        """Initialize Gemini client.
        
        Args:
            api_key: Google API key for Gemini
            model: Model to use for general tasks (default: gemini-1.5-flash)
        """
        self._client = genai.Client(api_key=api_key)
        self._model_name = model
        # Use gemini-3-pro-preview for high-reasoning tasks
        self._thinking_model = "gemini-3-pro-preview"
        self._mode = "planning"
    
    def set_mode(self, mode: str) -> None:
        """Set the agent mode (planning, coding, reflection).
        
        This changes the system prompt for subsequent messages.
        """
        if mode not in self.SYSTEM_PROMPTS:
            raise ValueError(f"Unknown mode: {mode}. Use: {list(self.SYSTEM_PROMPTS.keys())}")
        self._mode = mode

    def switch_model(self, model_name: str) -> None:
        """Switch the underlying Gemini model."""
        print(f"  🔄 Switching model from {self._model_name} to {model_name}")
        self._model_name = model_name
        
    def get_available_models(self) -> list[str]:
        """Get list of supported models."""
        return [
            "gemini-3-pro-preview",
        ]

    
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
                
                # Rate Limit Handling (429)
                if "429" in error_str or "resource" in error_str or "quota" in error_str:
                    if attempt < retries:
                        delay = 60  # Wait 60s as suggested by API
                        print(f"  ⚠️ Rate limit hit. Waiting {delay}s...")
                        await asyncio.sleep(delay)
                    else:
                        raise
                
                # Model Not Found Handling (404)
                elif "404" in error_str and "not found" in error_str and "model" in error_str:
                    print(f"  ⚠️ Model {use_model} not found/supported. Attempting switch...")
                    
                    # Try next available model
                    available = self.get_available_models()
                    current_idx = -1
                    if use_model in available:
                        current_idx = available.index(use_model)
                    
                    next_idx = (current_idx + 1) % len(available)
                    next_model = available[next_idx]
                    
                    # Avoid infinite loop if all fail
                    if next_model == use_model or attempt >= len(available):
                        print("  ❌ All models failed.")
                        raise
                        
                    print(f"  🔄 Switching to fallback: {next_model}")
                    if model is None: # If using default model, update it permanently
                        self._model_name = next_model
                    model = next_model # Update for next loop iteration
                    continue
                    
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
        available_extensions: str = "",
        conversation_context: str = ""
    ) -> dict:
        """Create a plan to achieve a goal.
        
        Args:
            goal: What to accomplish
            environment_info: Current environment description
            available_extensions: List of existing extensions
            conversation_context: Recent conversation history
            
        Returns:
            Plan as a structured dict
        """
        self.set_mode("planning")
        
        context = f"""## Environment
{environment_info}

## Conversation History
{conversation_context or "No recent conversation."}

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
5. For questions/knowledge requests WITH NO FILE OPERATIONS: create ONE step with action "complete" and put your full answer in "details"
6. NEVER use "reflect" when you need to CREATE, WRITE, SAVE, or MODIFY files - use "use_capability" with fs.write instead!

Available actions:
- "execute_extension": Run an existing extension (USE THIS if one exists that fits the task!)
- "use_capability": Execute a single capability (fs.read, fs.write, net.fetch, shell.run, etc.)
- "create_extension": Build a Python extension for complex multi-step logic (only if no existing extension fits)
- "complete": Mark goal as done (ALWAYS comes LAST, after work steps) - put the ACTUAL ANSWER in "details"
- "fail": Goal cannot be achieved with available capabilities (Use ONLY as absolute last resort after trying alternatives)

DECISION GUIDE:
- User asks to WRITE/SAVE/CREATE a file → use "use_capability" with fs.write, then "complete"
- User asks to READ a file → use "use_capability" with fs.read, then "complete"
- User asks a question (no file ops) → use only "complete" with answer in details
- User wants something AND to save it → use "use_capability" to save, then "complete"

CRITICAL - EXTENSIONS vs FILES:
- "save as EXTENSION" or "create extension" or "register extension" → use "create_extension" action (NOT fs.write!)
  - Extensions are stored in the agent's database and can be listed/run later via the CLI
  - Extensions are reusable code modules with metadata (name, description, version, capabilities)
- "save as FILE" or "write to file" → use "use_capability" with fs.write
  - Files are just saved to disk, NOT registered in the extension system

WRONG: User says "save it as an extension" → {{action: "use_capability", capabilities_needed: ["fs.write"]}} ← NEVER!
RIGHT: User says "save it as an extension" → {{action: "create_extension", details: "script that..."}}

WRONG: {{"action": "reflect", "details": "Generate content..."}} ← NEVER do this for file operations!
RIGHT: {{"action": "use_capability", "capabilities_needed": ["fs.write"], "params": {{"path": "file.txt", "content": "actual content"}}}}

For "execute_extension", include the extension_name:
{{"action": "execute_extension", "extension_name": "my_extension", "details": "Running the extension"}}

For "use_capability", include params:
{{"action": "use_capability", "capabilities_needed": ["fs.write"], "params": {{"path": "output.md", "content": "# Title\\n\\nContent here"}}}}

Respond with JSON:
{{
    "goal": "restated goal",
    "analysis": "brief analysis (2-3 sentences max)",
    "steps": [
        {{
            "action": "execute_extension|use_capability|create_extension|complete|fail",
            "extension_name": "name if execute_extension",
            "details": "description or answer content (PUT FULL ANSWER HERE for complete action)",
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



