import os
import requests
import logging
import time
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from requests_toolbelt.multipart.encoder import MultipartEncoder, MultipartEncoderMonitor
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Параметры
api_key = '450890z9nb025woa4945z4'
upload_folder = '/var/bongacams/tosent'
max_workers = 10  # Максимальное количество параллельных загрузок
wait_time = 10  # Время ожидания после последней модификации перед загрузкой
upload_timeout = 600  # Максимальное время, отведенное на загрузку файла, в секундах
check_interval = 60  # Интервал проверки новых файлов в секундах
ssl_retry_interval = 5  # Интервал повторных попыток после ошибок SSL
ssl_max_retries = 3  # Максимальное количество повторных попыток при ошибках SSL

# Настройка логирования
log_filename = f"/var/bongacams/uploadlog_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(filename=log_filename, level=logging.DEBUG,  # Уровень логирования DEBUG для максимального логирования
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Настройка стратегии повторных попыток с увеличенным временем ожидания и backoff_factor
retry_strategy = Retry(
    total=3,  # Уменьшаем количество повторных попыток
    backoff_factor=2,  # Увеличиваем backoff_factor для увеличения времени ожидания между попытками
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],
    respect_retry_after_header=True  # Учитывать заголовок Retry-After
)

adapter = HTTPAdapter(max_retries=retry_strategy)
http = requests.Session()
http.mount("https://", adapter)
http.mount("http://", adapter)

# Набор для отслеживания обрабатываемых и обработанных файлов
processed_files_lock = threading.Lock()
processed_files = set()

def get_upload_server():
    """
    Получает URL сервера для загрузки с использованием API doodapi.com.
    Если запрос неудачен, повторяет попытку до 3 раз с задержкой.
    """
    retry_attempts = 3
    backoff_time = 10  # Начальное время ожидания перед повторной попыткой

    for attempt in range(retry_attempts):
        try:
            response = http.get(f'https://doodapi.com/api/upload/server?key={api_key}', timeout=10)
            response.raise_for_status()  # Проверяем, что статус ответа успешен (2xx)
            logging.info("Получен URL сервера загрузки.")
            return response.json().get('result')  # Возвращаем URL сервера
        except requests.exceptions.SSLError as ssl_error:
            logging.error(f"SSL ошибка при получении URL сервера загрузки: {str(ssl_error)}. Попытка {attempt + 1} из {retry_attempts}.")
            time.sleep(ssl_retry_interval)  # Интервал между повторными попытками при ошибках SSL
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                logging.warning(f"Слишком много запросов (429). Увеличение времени ожидания перед повтором.")
                time.sleep(20)
                backoff_time *= 2  # Увеличиваем время ожидания при каждой ошибке 429
            else:
                logging.error(f"HTTP ошибка при получении URL сервера загрузки: {response.status_code}, ошибка: {str(e)}")
        except requests.exceptions.RequestException as e:
            logging.error(f"Ошибка запроса при получении URL сервера загрузки: {str(e)}")

        # Задержка перед повторной попыткой
        logging.info(f"Попытка {attempt + 1} не удалась. Повтор через {backoff_time} секунд.")
        time.sleep(backoff_time)

    logging.error("Не удалось получить URL сервера после нескольких попыток.")
    return None

def is_file_ready(file_path, wait_time=120):
    """
    Проверяет, прошел ли определенный период времени (wait_time) с последней модификации файла.
    """
    try:
        last_modified_time = os.path.getmtime(file_path)
        current_time = time.time()
        if current_time - last_modified_time > wait_time:
            logging.debug(f"Файл {file_path} готов к загрузке. Время с последней модификации: {current_time - last_modified_time:.2f} секунд.")
            return True
        else:
            logging.debug(f"Файл {file_path} не готов к загрузке. Время с последней модификации: {current_time - last_modified_time:.2f} секунд.")
    except Exception as e:
        logging.error(f"Ошибка при проверке готовности файла {file_path}: {str(e)}")
    return False

def upload_file(file_path):
    """
    Загружает видеофайл на сервер, используя API.
    """
    thread_name = threading.current_thread().name
    file_name = os.path.basename(file_path)

    logging.debug(f"Поток {thread_name} начал обработку {file_name}")

    if not is_file_ready(file_path, wait_time):
        logging.debug(f"Файл {file_name} еще записывается. Пропуск загрузки.")
        return False

    upload_url = get_upload_server()
    if not upload_url:
        logging.error(f"Не удалось получить URL загрузки для {file_name}")
        return False

    if not os.path.exists(file_path) or not file_path.endswith('.mp4'):
        logging.error(f"Файл {file_name} не существует или не является .mp4 файлом.")
        return False

    file_size = os.path.getsize(file_path)
    logging.debug(f"Начинаем загрузку {file_name}, размер: {file_size / (1024 * 1024):.2f} МБ")

    start_time = time.time()

    try:
        with open(file_path, 'rb') as f:
            encoder = MultipartEncoder(
                fields={'api_key': api_key, 'file': (file_name, f, 'video/mp4')}
            )
            monitor = MultipartEncoderMonitor(encoder)
            response = http.post(upload_url, data=monitor,
                                 headers={'Content-Type': monitor.content_type}, timeout=upload_timeout)
            response.raise_for_status()

    except requests.exceptions.SSLError as ssl_error:
        logging.error(f"SSL ошибка при загрузке файла {file_name}: {str(ssl_error)}")
        # Убираем файл из processed_files, если загрузка не удалась
        with processed_files_lock:
            processed_files.discard(file_path)
        return False
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка запроса при загрузке файла {file_name}: {str(e)}")
        with processed_files_lock:
            processed_files.discard(file_path)
        return False
    except Exception as e:
        logging.error(f"Неожиданная ошибка при загрузке файла {file_name}: {str(e)}")
        with processed_files_lock:
            processed_files.discard(file_path)
        return False
    finally:
        logging.debug(f"Поток {thread_name} завершил обработку {file_name}")

    end_time = time.time()
    elapsed_time = end_time - start_time
    average_speed = (file_size / 1024 / 1024) / elapsed_time  # Скорость в МБ/с

    if response.status_code in [200, 201, 206]:
        try:
            os.remove(file_path)
            logging.info(f"Файл {file_name} успешно загружен и удален. Время загрузки: {elapsed_time:.2f} секунд, средняя скорость: {average_speed:.2f} МБ/с")
            with processed_files_lock:
                processed_files.add(file_path)
        except OSError as e:
            logging.error(f"Ошибка при удалении файла {file_name}: {str(e)}")
        return True
    else:
        logging.error(f"Ошибка при загрузке файла {file_name}: HTTP {response.status_code}, текст ответа: {response.text}")
        with processed_files_lock:
            processed_files.discard(file_path)
        return False


def delete_old_temp_files(temp_folder, extensions=('.tmp.part', '.temp.tmp'), max_age=3600):
    """
    Удаляет файлы с указанными расширениями, если они не изменялись дольше max_age секунд.
    """
    current_time = time.time()
    try:
        for root, _, files in os.walk(temp_folder):
            for file in files:
                if file.endswith(extensions):
                    file_path = os.path.join(root, file)
                    last_modified_time = os.path.getmtime(file_path)
                    if current_time - last_modified_time > max_age:
                        try:
                            os.remove(file_path)
                            logging.info(f"Файл {file_path} не использовался более {max_age / 60} минут и был удален.")
                        except OSError as e:
                            logging.error(f"Ошибка при удалении файла {file_path}: {str(e)}")
    except Exception as e:
        logging.error(f"Ошибка при проверке и удалении временных файлов: {str(e)}")


def file_checker(executor):
    """
    Проверяет наличие файлов для загрузки каждые check_interval секунд и запускает процесс загрузки.
    Также проверяет и удаляет старые временные файлы с расширениями .tmp.part и .temp.tmp.
    """
    while True:
        try:
            logging.debug("Запуск проверки файлов для загрузки.")
            
            # Удаляем старые временные файлы
            delete_old_temp_files(upload_folder)

            files_to_upload = [
                os.path.join(root, file)
                for root, _, files in os.walk(upload_folder)
                for file in files
                if file.endswith('.mp4')
            ]

            with processed_files_lock:
                files_to_upload = [f for f in files_to_upload if f not in processed_files]

            for file in files_to_upload.copy():
                if os.path.getsize(file) < 50 * 1024 * 1024:
                    try:
                        os.remove(file)
                        logging.info(f"Файл {file} меньше 50 МБ и был удален.")
                        with processed_files_lock:
                            processed_files.add(file)
                        files_to_upload.remove(file)
                    except OSError as e:
                        logging.error(f"Ошибка при удалении файла {file}: {str(e)}")

            files_to_upload = [
                file for file in files_to_upload
                if os.path.exists(file) and os.path.getsize(file) >= 50 * 1024 * 1024 and is_file_ready(file, wait_time)
            ]

            if not files_to_upload:
                logging.info("Нет файлов, готовых для загрузки.")
            else:
                for file in files_to_upload:
                    with processed_files_lock:
                        processed_files.add(file)
                    executor.submit(upload_file, file)
                    time.sleep(5)

            logging.debug(f"Ожидание {check_interval} секунд перед следующей проверкой...")
            time.sleep(check_interval)
        except Exception as e:
            logging.error(f"Ошибка в процессе проверки файлов: {str(e)}")
            logging.info("Повтор проверки файлов после ошибки.")
            time.sleep(10)



if __name__ == "__main__":
    executor = ThreadPoolExecutor(max_workers=max_workers)
    checker_thread = threading.Thread(target=file_checker, args=(executor,))
    checker_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Получен сигнал прерывания. Завершаем работу.")
    finally:
        executor.shutdown(wait=True)
        checker_thread.join()
