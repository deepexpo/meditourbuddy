from fastapi import HTTPException


class AppError(HTTPException):
    """An HTTPException that also carries a machine-readable `code` and
    optional extra body fields (e.g. PROCEDURE_UNCLEAR's `choices`).

    Serialized by the handler in main.py as
    `{"detail": ..., "code": ..., **extra}`.
    """

    def __init__(self, status_code: int, detail: str, code: str, extra: dict | None = None):
        super().__init__(status_code=status_code, detail=detail)
        self.code = code
        self.extra = extra or {}
