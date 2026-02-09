import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.dirname(".")))

from src.extensions.registry import ExtensionRegistry
from src.models.extension import ExtensionMetadata

SOURCE_CODE = """
import os
import platform
import subprocess
import shutil

def extension_main():
    print("💰 Starting Financial Resource Audit...")
    print("-" * 40)
    
    # 1. Hardware Audit
    print("\\n[1] Hardware Analysis for Mining/Compute:")
    
    # CPU
    print(f"    CPU: {platform.processor()}")
    print(f"    Cores: {os.cpu_count()}")
    
    # RAM
    try:
        with open('/proc/meminfo') as f:
            total_mem = next(line for line in f if 'MemTotal' in line)
            print(f"    RAM: {total_mem.split(':')[1].strip()}")
    except:
        print("    RAM: Unknown")
        
    # GPU (Check for nvidia-smi)
    if shutil.which('nvidia-smi'):
        print("    GPU: NVIDIA Driver found. Checking details...")
        try:
            output = subprocess.check_output(['nvidia-smi', '-L'], text=True)
            print(f"    {output.strip()}")
            print("    ✅ Crypto Mining Potential: HIGH")
            print("    ✅ AI Model Hosting Potential: HIGH")
        except:
            print("    GPU: Error querying nvidia-smi")
    else:
        print("    GPU: No NVIDIA drivers found. (Mining potential low)")

    # 2. Digital Asset Scan
    print("\\n[2] Digital Asset Scan (Filesystem):")
    print("    Scanning home directory for wallets and keys...")
    
    home_dir = os.path.expanduser("~")
    interesting_files = []
    
    # Limit scan to safe depths to avoid long execution
    scan_extensions = ['.dat', '.key', '.pem', '.json', '.txt']
    keywords = ['wallet', 'bitcoin', 'ethereum', 'private', 'secret', 'seed', 'recovery']
    
    count = 0
    try:
        for root, dirs, files in os.walk(home_dir):
            # Skip hidden dirs except specific ones
            if '/.' in root and not '/.bitcoin' in root and not '/.ethereum' in root:
                continue
                
            for file in files:
                lower_name = file.lower()
                
                # Check for wallet files
                if 'wallet' in lower_name and (lower_name.endswith('.dat') or lower_name.endswith('.json')):
                    print(f"    Found potential wallet: {os.path.join(root, file)}")
                    interesting_files.append(file)
                
                # Check for key files
                elif any(lower_name.endswith(ext) for ext in scan_extensions):
                    if any(k in lower_name for k in keywords):
                        print(f"    Found interesting file: {os.path.join(root, file)}")
                        interesting_files.append(file)
            
            count += 1
            if count > 1000: # Safety limit for demo
                break
                
    except Exception as e:
        print(f"    Scan error: {e}")
        
    if not interesting_files:
        print("    No obvious wallet or key files found in quick scan.")

    print("-" * 40)
    print("✅ Audit Complete.")
    
    if interesting_files:
        return f"Found {len(interesting_files)} potential asset files."
    else:
        return "System audit complete. No direct digital assets found, but hardware specs analyzed."

"""

async def register_extension():
    data_dir = "data"
    if os.path.exists("/home/fluxx/Workspace/Delta/data"):
        data_dir = "/home/fluxx/Workspace/Delta/data"
        
    registry = ExtensionRegistry(f"{data_dir}/extensions.db")
    
    metadata = ExtensionMetadata(
        name="resource_asset_auditor",
        description="Audits system hardware and files for financial opportunities (mining, wallets).",
        version="1.0.0",
        required_capabilities=["fs.read", "fs.list"],
        tags=["audit", "financial", "system"]
    )
    
    await registry.register(metadata, SOURCE_CODE)
    print("Extension 'resource_asset_auditor' registered successfully.")

if __name__ == "__main__":
    asyncio.run(register_extension())
