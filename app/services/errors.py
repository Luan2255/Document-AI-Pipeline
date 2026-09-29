"""Represent expected document pipeline failures with safe public error codes."""


class DocumentProcessingError(Exception):
    """Carry an HTTP status and non-sensitive code for a processing failure."""

    def __init__(self, message: str, status_code: int, error_code: str) -> None:
        """Initialize a safe public message, HTTP status, and internal code."""

        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code