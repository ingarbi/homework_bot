import datetime
import json
import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup

import exceptions as err

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='tg_bot.log',
    format='%(asctime)s - %(levelname)s - %(message)s - %(name)s'

)
logger = logging.getLogger(__name__)
logger.addHandler(
    logging.StreamHandler(sys.stdout)
)


def check_tokens():
    """Проверяет существование переменных."""
    return all([TELEGRAM_TOKEN, PRACTICUM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляем сообщение в Telegram."""
    try:
        button = ReplyKeyboardMarkup([['/check_homework']],
                                     resize_keyboard=True)
        logger.debug(
            f'Сообщение в Telegram отправлено: {message}')
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
            reply_markup=button,
        )
        logger.debug(
            f'Сообщение в Telegram отправлено: {message}')
    except telegram.TelegramError as telegram_error:
        logger.error(
            f'Сообщение в Telegram не отправлено: {telegram_error}')


def get_api_answer(timestamp):
    """Получаем статус ответа."""
    headers = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
    params = {'from_date': timestamp}
    try:
        logger.info(
            f'Запрашивается url = {ENDPOINT},'
            f'headers = {headers},'
            f'params = {params}'
        )
        response = requests.get(ENDPOINT, headers=headers, params=params)
    except requests.exceptions.ConnectionError as error:
        raise SystemExit(error)
    except requests.exceptions.Timeout as error:
        raise SystemExit(error)
    except requests.exceptions.RequestException as error:
        raise err.RequestError(error)
    if response.status_code != HTTPStatus.OK:
        raise err.StatusNot200Error(f'Ошибка, Url {ENDPOINT} недоступен')
    try:
        return response.json()
    except json.decoder.JSONDecodeError:
        raise err.ResponseError('Это не JSON формат')


def check_response(response):
    """Проверяем валидность полученных данных."""
    logging.debug('Начало проверки ответа запроса')

    if type(response) is not dict:
        raise TypeError('Ошибка в типе ответа API')
    if not response:
        raise err.EmptyAPIResponse('Ошибка, пустой ответ от API')
    if 'homeworks' not in response:
        raise KeyError(
            'Ошибка, в ответе нет ключа "homeworks"'
        )
    if 'current_date' not in response:
        raise KeyError(
            'Ошибка, в ответе нет ключа "current_date"'
        )
    if len(response['homeworks']) == 0:
        raise KeyError(
            'Ошибка, во временном диапозоне для "current_date"'
        )
    if type(response.get('homeworks')) is not list:
        raise TypeError('Ошибка, тип API не соответствует "list"')
    return response.get('homeworks')


def parse_status(homework):
    """Проверяем состояние статуса домашней работы."""
    try:
        homework_name = homework['homework_name']
        homework_status = homework['status']
    except KeyError:
        raise KeyError('Ошибка, несуществующий ключ')
    if homework_status not in HOMEWORK_VERDICTS:
        raise err.NotExistingVerdictError(
            f'Неизвестный статус работы - {homework_status}'
        )
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time() / 10)
    previous_status = ''
    initial_error = ''
    now = datetime.datetime.now()
    send_message(
        bot, f'Запустился в {now}'
    )
    if not check_tokens():
        logging.critical(
            'Ошибка, отсутствуют необходимые переменные окружения'
        )
        raise SystemExit(
            'Ошибка, отсутствуют необходимые переменные окружения'
        )

    while True:
        try:
            response = get_api_answer(timestamp)
            timestamp = response.get('current_date')
            homework = check_response(response)
            message = parse_status(homework[0])
            if message != previous_status:
                send_message(bot, message)
            time.sleep(RETRY_PERIOD)
        except Exception as error:
            logger.critical(f'Ошибка в статусe и валидности ответа {error}')
            error_message = f'Сбой в работе программы: {error}'
            if error_message != initial_error:
                send_message(bot, error_message)
                initial_error = error_message
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
