from fastapi import FastAPI
from .routers import publico, administrador
from .empleado import empleado

app = FastAPI()
app.include_router(publico)
app.include_router(administrador)
app.include_router(empleado)