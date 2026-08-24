import uvicorn
from app.config import settings
from seed_data import seed_database

if __name__ == "__main__":
    # Seed default data on start if empty
    seed_database()
    
    print(f"============================================================")
    print(f" Starting {settings.APP_NAME}")
    print(f" Access URL: http://localhost:{settings.PORT}")
    print(f" API Docs:   http://localhost:{settings.PORT}/docs")
    print(f"============================================================")
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False
    )
