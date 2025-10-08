"""
JobHire.AI FastAPI Backend - Legacy Entry Point
This file now redirects to the new enterprise architecture.
"""

import sys
import os
from pathlib import Path

# Add the new src path to Python path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

# Import the new enterprise application
try:
    from src.jobhire.main import app
except ImportError:
    # Fallback for different import paths
    import jobhire.main
    app = jobhire.main.app

# For backward compatibility, expose the app
__all__ = ["app"]

# Print migration notice
print("\n" + "="*60)
print("🚀 JobHire.AI Backend - Enterprise Architecture")
print("="*60)
print("✅ Successfully migrated to new enterprise structure!")
print("📂 Location: /src/jobhire/")
print("📋 API Docs: http://localhost:8000/docs")
print("🔗 Health: http://localhost:8000/api/v1/health")
print("="*60 + "\n")


if __name__ == "__main__":
    import uvicorn
    print("🔄 Starting server via legacy entry point...")
    print("💡 Recommended: Use 'python scripts/start_server.py' for optimal experience")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)