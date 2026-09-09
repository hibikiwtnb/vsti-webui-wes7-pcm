class AppError(Exception):
    def __init__(self, message: str, code: str, status_code: int) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class ValidationError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, "VALIDATION_ERROR", 422)


class ConflictError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, "CONFLICT", 409)


class NotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, "NOT_FOUND", 404)


class ServiceUnavailableError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, "SERVICE_UNAVAILABLE", 503)
