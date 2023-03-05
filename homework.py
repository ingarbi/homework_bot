import datetime
import logging
import os
import sys
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


class CustomExceptions(Exception):
    """Содержит возможные ошибки."""

    class EmptyAPIResponse(Exception):
        """Ошибка, ответ пустой."""
    class NotExistingVerdictError(Exception):
        """Ошибка, несущуствующий вердикт ревью."""
    class RequestError(Exception):
        """Ошибка при запросе."""
    class StatusNot200Error(Exception):
        """Ошибка, ответ сервера не равен 200."""


def check_tokens():
    """Проверяет существование переменных."""
    return all([TELEGRAM_TOKEN, PRACTICUM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляем сообщение в Telegram."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(
            f'Сообщение в Telegram отправлено: {message}')
    except telegram.TelegramError as telegram_error:
        logger.error(
            f'Сообщение в Telegram не отправлено: {telegram_error}')


def get_api_answer(timestamp):
    """Получает статус ответа."""
    headers = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
    payload = {'from_date': timestamp}
    try:
        logging.info(
            f'Запрашивается url = {ENDPOINT},'
            f'headers = {headers},'
            f'params = {payload}'
        )
        response = requests.get(url=ENDPOINT, headers=headers, params=payload)
        if response.status_code == HTTPStatus.OK:
            return response.json()
        else:
            logger.error(
                'Ошибка при получении данных, статус ответа:'
                f'{response.status_code}'
            )
            raise CustomExceptions.StatusNot200Error(
                f'Ошибка, Url {ENDPOINT} недоступен'
            )
    except requests.exceptions.RequestException as request_error:
        logger.error(F'Ошибка при запросе {request_error}')
        raise CustomExceptions.RequestError(
            'Ошибка, проверьте параметры запроса: '
            f'url = {ENDPOINT}, headers = {headers}, payload = {payload}'
        )


def check_response(response):
    """Проверяем валидность полученных данных."""
    logging.debug('Начало проверки ответа запроса')
    if not isinstance(response, dict):
        logger.error(f'Ошибка в ответе: {response}')
        raise TypeError('Ошибка в типе ответа API')
    if 'homeworks' not in response:
        logger.error(f'Ошибка, ответ с запроса пришел пустым: {response}')
        raise CustomExceptions.EmptyAPIResponse('Пустой ответ от API')
    homework_verdict = response['homeworks'][0].get('status')
    if homework_verdict not in HOMEWORK_VERDICTS:
        logger.error(f'Ошибка, несущуствующий статус: {homework_verdict}')
        raise CustomExceptions.NotExistingVerdictError(
            f'Ошибка, несущуствующий статус: {homework_verdict}'
        )
    return response['homeworks'][0]


def parse_status(homework):
    """Проверяет состояние статуса."""
    if 'homework_name' not in homework:
        logger.error('Ошибка, "homework_name" отсутсвует')
        raise KeyError('В ответе отсутсвует ключ homework_name')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        logger.error(f'Неизвестный статус работы - {homework_status}')
        raise CustomExceptions.NotExistingVerdictError(
            f'Неизвестный статус работы - {homework_status}'
        )
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Отсутствует необходимые переменные окружения')
        sys.exit('Бот остановлен из-за отсутсвия всех переменных')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    now = datetime.datetime.now()
    send_message(
        bot, f'Начал работать с {now}'
    )
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks)
                send_message(bot, message)
                logger.info(
                    'Нет изменений, через 10 минут повторная проверка статуса'
                )
                time.sleep(RETRY_PERIOD)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logger.critical(message)
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        filename='tg_bot.log',
        format='%(asctime)s - %(levelname)s - %(message)s - %(name)s'
    )
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler('my_log.log', maxBytes=5000, backupCount=3)
    logger.addHandler(handler)
    main()
