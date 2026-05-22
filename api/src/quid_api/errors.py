from __future__ import annotations

from enum import StrEnum


class RepositoryErrorCode(StrEnum):
    NOT_FOUND = "NOT_FOUND"
    IMMUTABLE = "IMMUTABLE"
    VALIDATION = "VALIDATION"


class RepositoryError(Exception):
    def __init__(self, code: RepositoryErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def http_status_for(code: RepositoryErrorCode) -> int:
    match code:
        case RepositoryErrorCode.NOT_FOUND:
            return 404
        case RepositoryErrorCode.IMMUTABLE:
            return 409
        case RepositoryErrorCode.VALIDATION:
            return 422
