from uuid import uuid4

from fastapi import FastAPI, Request

from .models import Health
from .routers import admin, portal

app = FastAPI()


@app.middleware('http')
async def request_identifier(request: Request, call_next):
    request.state.request_id = str(uuid4())
    response = await call_next(request)
    response.headers['X-Request-ID'] = request.state.request_id
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.get('/api/health', response_model=Health, tags=['Salud'])
def health():
    return {'estado': 'ok'}


app.include_router(portal)
app.include_router(admin)