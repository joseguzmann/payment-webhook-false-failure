import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./local.db")
# Where the API reaches the gateway, and where the gateway sends its callbacks.
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8001")
CALLBACK_URL = os.getenv("CALLBACK_URL", "http://localhost:8000/webhooks/paylink")
