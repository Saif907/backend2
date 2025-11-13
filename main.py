from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.libs.config import settings
from app.auth.router import router as auth_router
from app.apis.chat_router import router as chat_router
from app.apis.trade_router import router as trade_router
from app.apis.ai_router import router as ai_router

# Initialize FastAPI app
app = FastAPI(
    title="Trading Journal API",
    description="AI-powered trading journal backend",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS - Must be before routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:8080", 
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8080"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(trade_router, prefix="/api")
app.include_router(ai_router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Trading Journal API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT
    }


# Handle OPTIONS for all routes
@app.options("/{full_path:path}")
async def options_handler():
    return {"message": "OK"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.ENVIRONMENT == "development"
    )