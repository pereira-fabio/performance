from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "Performance"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
    API_AUTH_TOKEN: str = os.getenv("API_AUTH_TOKEN", "")
    
    # Storage and DB paths (designed for TrueNAS NFS/SMB mount or local LXC)
    DATA_DIR: str = os.getenv("DATA_DIR", "/data")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:////data/peakpace.db")
    
    # User physiology defaults (can be overridden via Settings API)
    DEFAULT_MAX_HR: int = 190
    DEFAULT_RESTING_HR: int = 50
    DEFAULT_LTHR: int = 168  # Lactate Threshold Heart Rate
    DEFAULT_THRESHOLD_PACE_SEC: float = 240.0  # 4:00 min/km in seconds (FTP pace)
    DEFAULT_GENDER: str = "male"  # "male" or "female" for Banister TRIMP weighting
    
    # Terrain model used to recover elevation for devices that record none.
    # Directory of SRTM .hgt (or .hgt.zip) tiles; empty disables the lookup.
    DEM_DIR: str = os.getenv("DEM_DIR", "/data/dem")

    # A locally hosted language model that writes commentary on training. It
    # only ever rephrases figures this server computed; nothing depends on it
    # being reachable.
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

    # Aerobic Decoupling thresholds
    DECOUPLING_WINDOW_MIN_DURATION_SEC: int = 1200 # Minimum 20 mins for valid decoupling calculation
    
    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
