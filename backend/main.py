from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException

from .utils import (
    verify_token_blacklist,
    http_exception_handler,
    server_exception_handler,
    validation_exception_handler,
)
from .database import engine
from .api_routes import authRouter, articlesRouter, documentsRouter
from .models.base import Base

Base.metadata.create_all(bind=engine)


app = FastAPI()

# register exception handlers
app.add_exception_handler(Exception, server_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)


# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.add_middleware(BaseHTTPMiddleware, dispatch=verify_token_blacklist)

# register api modules
app.include_router(authRouter)
app.include_router(articlesRouter)
app.include_router(documentsRouter, prefix="/documents", tags=["Documents"])  


@app.get("/")
def read_root():
    return {"message": "Hello, World!"}
