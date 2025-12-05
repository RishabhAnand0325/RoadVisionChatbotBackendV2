import uvicorn

# This file is the main entry point for running the application.
# It launches the Uvicorn server, which runs the FastAPI app defined in `app/main.py`.

if __name__ == "__main__":
    print("\n" + "="*70)
    print("🚀 DEVELOPMENT RAG BACKEND SERVER (FastAPI)")
    print("="*70)
    print(f"✅ Starting application...")
    print("🌐 Uvicorn server running on http://0.0.0.0:5000")
    print("📚 API docs available at http://0.0.0.0:5000/docs")
    print("="*70 + "\n")
    
    # Uvicorn is the ASGI server that runs our FastAPI application.
    # It is instructed to find the `app` object inside the `app.main` module.
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=5001,
        reload=True  # Enable auto-reloading for development
    )
