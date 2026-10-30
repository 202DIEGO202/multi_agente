from fastapi import FastAPI
from .routers import publico, administrador

app = FastAPI()
app.include_router(publico)
app.include_router(administrador)