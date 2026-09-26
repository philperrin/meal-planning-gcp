"""
Custom exceptions for the Meal Planning Assistant.
"""

class AppError(Exception):
    """Base application exception with HTTP status code support."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

class AuthRequiredError(AppError):
    """Raised when an operation requires Google Workspace authentication."""
    def __init__(self, message: str = "Google Workspace authentication required."):
        super().__init__(message, status_code=401)

class GeminiError(AppError):
    """Raised when the Gemini API encounters an unrecoverable error."""
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message, status_code=status_code)

class GeminiQuotaError(GeminiError):
    """Raised when Gemini API quota or rate limits are reached (429)."""
    def __init__(self, message: str = "Gemini API rate limit or quota exceeded."):
        super().__init__(message, status_code=429)

class StorageError(AppError):
    """Raised when database read/write operations fail."""
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message, status_code=status_code)
