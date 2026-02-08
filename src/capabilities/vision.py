"""Vision capability - allows the agent to see the screen."""

import base64
import io
import mss
from src.capabilities.base import Capability

class VisionCapability(Capability):
    """Capability to capture screen content."""
    
    name = "vision.capture_screen"
    description = "Capture a screenshot of the primary monitor"
    
    async def execute(self, **kwargs) -> dict:
        """Capture screenshot and return as base64 string.
        
        Returns:
            dict: {"success": bool, "image_data": str (base64 png), "size": tuple}
        """
        try:
            with mss.mss() as sct:
                # Capture primary monitor
                monitor = sct.monitors[1]
                screenshot = sct.grab(monitor)
                
                # Convert to PNG
                img_bytes = mss.tools.to_png(screenshot.rgb, screenshot.size)
                
                # Encode to base64
                b64_data = base64.b64encode(img_bytes).decode("utf-8")
                
                return {
                    "success": True,
                    "image_data": b64_data,
                    "mime_type": "image/png",
                    "width": screenshot.width,
                    "height": screenshot.height
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
