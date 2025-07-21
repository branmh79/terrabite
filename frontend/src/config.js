// Configuration file for TerraBite frontend endpoints
// Set this to true for local development, false for production
const LOCAL_DEVELOPMENT = false;

// Base URLs
const BACKEND_BASE_URL = LOCAL_DEVELOPMENT 
  ? "http://localhost:8000" 
  : "https://terrabite.onrender.com";

// API Endpoints
export const API_ENDPOINTS = {
  predict: `${BACKEND_BASE_URL}/predict`,
  progress: `${BACKEND_BASE_URL}/progress`,
  results: `${BACKEND_BASE_URL}/results`,
  tiles: `${BACKEND_BASE_URL}/tiles`,
  root: `${BACKEND_BASE_URL}/`
};

// Development helpers
export const isLocal = () => LOCAL_DEVELOPMENT;
export const getBackendUrl = () => BACKEND_BASE_URL; 