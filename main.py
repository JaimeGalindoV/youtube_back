import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Leemos el origen permitido desde una variable de entorno
# Si no existe, por seguridad no permitirá nada o puedes poner un default de desarrollo
ALLOWED_ORIGIN = os.getenv("FRONTEND_URL")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Holi desde el backend"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}