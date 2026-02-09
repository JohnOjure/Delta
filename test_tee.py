import sys
import io
import contextlib

# Inline TeeIO implementation from sandbox.py
class TeeIO:
    """Writes to a buffer and the original stream."""
    def __init__(self, original_stream):
        self.original_stream = original_stream
        self.buffer = io.StringIO()
        
    def write(self, s):
        self.original_stream.write(s)
        self.original_stream.flush()
        return self.buffer.write(s)
        
    def flush(self):
        self.original_stream.flush()
        self.buffer.flush()
    
    def getvalue(self):
        return self.buffer.getvalue()

def test_tee():
    print("Beginning TeeIO Test...")
    
    original_stdout = sys.stdout
    capture = TeeIO(original_stdout)
    
    print("Redirecting stdout...")
    with contextlib.redirect_stdout(capture):
        print("This should appear on screen AND be captured.")
        sys.stdout.write("Direct write test.\n")
        
    print("Restored stdout.")
    
    captured_content = capture.getvalue()
    print(f"\nCaptured Content Length: {len(captured_content)}")
    print(f"Captured Content:\n---\n{captured_content}\n---")
    
    if "This should appear on screen" in captured_content and "Direct write test" in captured_content:
        print("SUCCESS: Content was captured.")
    else:
        print("FAILURE: Content missing from capture.")

if __name__ == "__main__":
    test_tee()
