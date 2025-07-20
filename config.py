# Configuration file for TerraBite endpoints
# Set this to True for local development, False for production
LOCAL_DEVELOPMENT = False

# Base URLs
if LOCAL_DEVELOPMENT:
    BACKEND_BASE_URL = "http://localhost:8000"
    FRONTEND_BASE_URL = "http://localhost:3000"
else:
    BACKEND_BASE_URL = "https://terrabite.onrender.com"
    FRONTEND_BASE_URL = "https://www.terrabite.dev"

# API Endpoints
API_ENDPOINTS = {
    "predict": f"{BACKEND_BASE_URL}/predict",
    "progress": f"{BACKEND_BASE_URL}/progress",
    "results": f"{BACKEND_BASE_URL}/results",
    "tiles": f"{BACKEND_BASE_URL}/tiles",
    "root": f"{BACKEND_BASE_URL}/"
}

# CORS settings for backend
CORS_ORIGINS = [
    "http://localhost:3000",  # React dev server
    "http://localhost:3001",  # Alternative React port
    "https://www.terrabite.dev",  # Production frontend
]

# Development helpers
def is_local():
    """Check if running in local development mode"""
    return LOCAL_DEVELOPMENT

def get_backend_url():
    """Get the current backend base URL"""
    return BACKEND_BASE_URL

def get_frontend_url():
    """Get the current frontend base URL"""
    return FRONTEND_BASE_URL 