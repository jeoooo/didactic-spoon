class AppError(Exception):
    """Base class for app errors that map to a specific HTTP status + error code."""

    status_code: int = 400
    error_code: str = "error"

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class ValidationAppError(AppError):
    status_code = 422
    error_code = "validation_error"


class NotFoundAppError(AppError):
    status_code = 404
    error_code = "not_found"


class UpstreamAppError(AppError):
    status_code = 502
    error_code = "llm_error"
