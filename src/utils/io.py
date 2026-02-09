import sys
import io

class TeeIO(io.StringIO):
    """A file-like object that writes to a buffer and the original stream."""
    
    def __init__(self, original_stream):
        super().__init__()
        self.original_stream = original_stream
        
    def write(self, s):
        self.original_stream.write(s)
        self.original_stream.flush() # Ensure immediate output
        return super().write(s)
        
    def flush(self):
        self.original_stream.flush()
        super().flush()
