"""
Application entry point
"""

import os
import uvicorn
from app.core.config import settings
from app.main import app

if __name__ == "__main__":
    # Railway sets PORT environment variable
    port = int(os.getenv("PORT", settings.PORT))
    uvicorn.run(
        app,
        host=settings.HOST,
        port=port,
        reload=settings.DEBUG
    )
