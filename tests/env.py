import os

LB_URL = os.getenv("LB_URL", "http://localhost:8000")
APP1_URL = os.getenv("APP1_URL", "http://localhost:8001")
APP2_URL = os.getenv("APP2_URL", "http://localhost:8002")

# Optional short-window instance for testing window reset quickly.
APP_SHORT_URL = os.getenv("APP_SHORT_URL", "")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")