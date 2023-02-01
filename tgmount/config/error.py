from typing import Type
from tgmount import vfs
from tgmount.config.util import get_type_name

from tgmount.util import col, none_fallback


class ConfigError(Exception):
    def __init__(self, message: str, error: Exception | None = None) -> None:
        self.message = message
        self.error = error
        super().__init__(message)

    def get_first_exception(self):
        error = self.error

        if isinstance(error, ConfigError):
            return error.get_first_exception()

        return error


class ConfigErrorWithPath(ConfigError):
    def __init__(
        self,
        path: str | list[str],
        error: ConfigError | Exception,
        message: str | None = None,
    ) -> None:

        if isinstance(path, str):
            self.path = vfs.napp(path, True)
        else:
            self.path = path
        message = None
        super().__init__(
            none_fallback(
                message,
                f"An error happened at {vfs.path_join(*self.path)}: {error.message if isinstance(error, ConfigError) else str(error)}",
            ),
            error,
        )

    def __repr__(self) -> str:
        return f"Error at {vfs.path_join(*self.path)}: {self.message}"


class TypecheckError(ConfigError):
    def __init__(
        self, expected_type: Type, actual_type: Type, message: str | None = None
    ) -> None:
        self.expected_type = expected_type
        self.actual_type = actual_type
        super().__init__(
            none_fallback(
                message,
                f"Expected type: {get_type_name(self.expected_type)}, actual type: {get_type_name(self.actual_type)}",
            ),
            None,
        )

    # def __repr__(self) -> str:
    #     return super().__repr__()


class MissingKeyError(ConfigError):
    def __init__(
        self,
        key: str,
        message: str | None = None,
    ) -> None:
        self.key = key
        super().__init__(none_fallback(message, f"Missing key: {key}"), None)


class ConfigPropertyError(ConfigError):
    def __init__(self, prop: str, error: Exception, message: str | None = None) -> None:
        super().__init__(
            none_fallback(
                message,
                f"Property `{prop}` error: {str(error)}",
            ),
            error,
        )
        self.property = prop
