

class EmptyAPIResponse(Exception):
    """Ошибка, ответ пустой."""


class MissingVariables(Exception):
    """Ошибка, отсутсвует обязательные переменные."""


class NotExistingVerdictError(Exception):
    """Ошибка, несущуствующий вердикт ревью."""


class RequestError(Exception):
    """Ошибка при запросе."""


class ResponseError(Exception):
    """Ошибка при запросе."""


class SendingError(Exception):
    """Ошибка во время отправки."""


class StatusNot200Error(Exception):
    """Ошибка, ответ сервера не равен 200."""
