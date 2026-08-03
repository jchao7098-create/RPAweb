class LearningError(Exception):
    status_code = 400

    def __init__(self, message='Learning request failed'):
        super().__init__(message)
        self.message = message


class LearningValidationError(LearningError):
    status_code = 422


class LearningConflictError(LearningError):
    status_code = 409


class LearningForbiddenError(LearningError):
    status_code = 403


class LearningNotFoundError(LearningError):
    status_code = 404


class LearningUnauthorizedError(LearningError):
    status_code = 401
