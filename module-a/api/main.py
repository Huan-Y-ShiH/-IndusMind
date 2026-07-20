"""IndusMind Module A - Prediction Engine API."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers import prediction

app = FastAPI(
    title="IndusMind Module A - Prediction Engine",
    description="LSTM+Transformer RUL prediction and anomaly detection API",
    version="0.1.0",
)

# CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(prediction.router)

@app.get("/")
async def root():
    return {"service": "IndusMind Module A", "status": "running"}
