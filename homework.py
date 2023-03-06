import datetime
import logging
import os
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler
from telegram import ReplyKeyboardMarkup
import exceptions as err
import json

import requests
import telegram
from dotenv import load_dotenv

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
handler = RotatingFileHandler('my_log.log', maxBytes=5000, backupCount=3)
logger.addHandler(handler)


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
        logging.info(
            f'Запрашивается url = {ENDPOINT},'
            f'headers = {headers},'
            f'params = {params}'
        )
        response = requests.get(ENDPOINT, headers=headers, params=params)
    except requests.exceptions.ConnectionError as error:
        logger.error('Ошибка с подключением, попробуйте ещё раз')
        raise SystemExit(error)
    except requests.exceptions.Timeout as error:
        logger.error('Ошибка, ожидание ответа превысило лимит')
        raise SystemExit(error)
    except requests.exceptions.RequestException as error:
        logger.error('Ошибка запроса')
        raise err.RequestError(error)

    if response.status_code != HTTPStatus.OK:
        logger.error(
            'Ошибка при получении данных, статус ответа:'
            f'{response.status_code}'
        )
        raise err.StatusNot200Error(
            f'Ошибка, Url {ENDPOINT} недоступен'
        )
    try:
        return response.json()
    except json.decoder.JSONDecodeError:
        logger.error('Это не JSON формат')


def check_response(response):
    """Проверяем валидность полученных данных."""
    logging.debug('Начало проверки ответа запроса')

    if type(response) is not dict:
        logger.error(f'Ошибка в ответе: {response}')
        raise TypeError('Ошибка в типе ответа API')
    if not response:
        logger.error(f'Ошибка, ответ с запроса пришел пустым: {response}')
        raise err.EmptyAPIResponse('Ошибка, пустой ответ от API')
    if 'homeworks' not in response:
        logger.error('Ошибка, в ответе нет ключа "homeworks"')
        raise KeyError('Ошибка, в ответе нет ключа "homeworks"')
    if type(response.get('homeworks')) is not list:
        logger.error('Ошибка, тип API не соответствует "list"')
        raise TypeError('Ошибка, тип API не соответствует "list"')
    homework_verdict = response['homeworks'][0].get('status')
    if homework_verdict not in HOMEWORK_VERDICTS:
        logger.error(f'Ошибка, несущуствующий статус: {homework_verdict}')
        raise err.NotExistingVerdictError(
            f'Ошибка, несущуствующий статус: {homework_verdict}'
        )
    return response.get('homeworks')


def parse_status(homework):
    """Проверяем состояние статуса домашней работы."""
    try:
        homework_name = homework['homework_name']
        homework_status = homework['status']
    except KeyError:
        logger.error('Ошибка, несуществующий ключ')
        raise KeyError('Ошибка, несуществующий ключ')
    if homework_status not in HOMEWORK_VERDICTS:
        logger.error(f'Неизвестный статус работы - {homework_status}')
        raise err.NotExistingVerdictError(
            f'Неизвестный статус работы - {homework_status}'
        )
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
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
            response = check_response(response)
            if response:
                message = parse_status(response[0])
            else:
                message = 'Нет новых статусов работ.'
            send_message(bot, message)
            logger.debug('Сообщение успешно отправлено')
            timestamp = int(time.time())
            time.sleep(RETRY_PERIOD)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.critical(message)
            send_message(bot, message)
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
