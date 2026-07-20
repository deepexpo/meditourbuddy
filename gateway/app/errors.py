from fastapi import HTTPException


class AppError(HTTPException):
    """An HTTPException that also carries a machine-readable `code`.

    Serialized by the handler in main.py as `{"detail": ..., "code": ...}`.
    """

    def __init__(self, status_code: int, detail: str, code: str):
        super().__init__(status_code=status_code, detail=detail)
        self.code = code
