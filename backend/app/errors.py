from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        self.status, self.code, self.message, self.details = status, code, message, details or {}


def body(code: str, message: str, details: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def install(app):
    @app.exception_handler(ApiError)
    async def _api(_: Request, exc: ApiError):
        return JSONResponse(status_code=exc.status, content=body(exc.code, exc.message, exc.details))

    @app.exception_handler(RequestValidationError)
    async def _val(_: Request, exc: RequestValidationError):
        errs = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
        return JSONResponse(status_code=400, content=body("VALIDATION_ERROR", "Some fields are missing or invalid.", {"errors": errs}))
