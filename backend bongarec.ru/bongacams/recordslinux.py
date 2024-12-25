import os
import random
import pandas as pd
import asyncio
import aiohttp
import logging
from datetime import datetime
import signal
from bs4 import BeautifulSoup

# Настройка логирования
log_filename = datetime.now().strftime("/var/bongacams/log_%Y%m%d_%H%M%S.txt")
logging.basicConfig(filename=log_filename, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Путь к CSV файлу
csv_file_path = '/var/bongacams/models.csv'

# Базовый URL
base_url = "https://ru5.bongacams.com/"

# Директория для сохранения стримов
output_dir = '/var/bongacams/recb/'
os.makedirs(output_dir, exist_ok=True)

# Глобальные переменные
active_models = {}  # Словарь для отслеживания активных записей
terminate_event = asyncio.Event()  # Флаг завершения

# Семафор для ограничения количества одновременно выполняемых задач на проверку
semaphore = asyncio.Semaphore(30)  # Устанавливаем значение 30

# Список всех активных задач
tasks = []

# Функция для генерации случайного User-Agent
def generate_random_user_agent():
    browsers = ['Mozilla/5.0', 'Opera/9.80', 'Mozilla/4.0', 'Mozilla/5.0 (Windows NT 6.1; WOW64)',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:79.0) Gecko/20100101 Firefox/79.0']
    operating_systems = [
        'Windows NT 10.0; Win64; x64', 'Macintosh; Intel Mac OS X 10_15_7', 'X11; Linux x86_64',
        'Windows NT 6.1; Win64; x64', 'Windows NT 6.3; Win64; x64'
    ]
    webkits = [
        'AppleWebKit/537.36 (KHTML, like Gecko)', 'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110',
        'AppleWebKit/537.36 (KHTML, like Gecko) Safari/537.36', 'KHTML, like Gecko', 'Trident/7.0; rv:11.0'
    ]
    browser_details = [
        'Chrome/91.0.4472.124 Safari/537.36', 'Safari/537.36', 'Edge/18.19041', 'OPR/74.0.3911.218', 'Firefox/79.0'
    ]

    user_agent = f"{random.choice(browsers)} ({random.choice(operating_systems)}) {random.choice(webkits)} {random.choice(browser_details)}"
    logging.debug(f"Generated User-Agent: {user_agent}")
    return user_agent

# Функция для проверки существования и доступности модели
async def check_if_model_exists(session, model_url):
    try:
        headers = {'User-Agent': generate_random_user_agent()}
        async with session.get(model_url, allow_redirects=True, headers=headers, timeout=30) as response:
            if str(response.url) != model_url:
                logging.info(f"Model does not exist: redirected to {response.url}")
                return False

            content = await response.text()
            soup = BeautifulSoup(content, 'html.parser')
            if 'Profile not found' in soup.text or (soup.title and 'Welcome to BongaCams' in soup.title.text):
                logging.info(f"Model does not exist: {model_url}")
                return False

            if str(response.url) == base_url:
                logging.info(f"Model does not exist and was redirected to the main page: {model_url}")
                return False

            return True
    except aiohttp.ClientError as e:
        logging.error(f"Network error checking model existence: {str(e)}")
        return False
    except asyncio.TimeoutError:
        logging.error(f"Timeout while checking model existence: {model_url}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error checking model existence: {str(e)}")
        return False

# Функция для проверки статуса модели
async def check_model_status(session, model_name, model_url, user_agent):
    if not await check_if_model_exists(session, model_url):
        logging.info(f"Model {model_name} is offline or does not exist.")
        return "offline"

    try:
        # Здесь мы только проверяем форматы, не прерываясь на одном фрагменте
        process = await asyncio.create_subprocess_exec(
            'yt-dlp',
            '--user-agent', user_agent,
            '--list-formats',
            '--quiet',
            '--no-warnings',
            model_url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        return_code = process.returncode
        if return_code != 0:
            logging.error(f"yt-dlp exited with code {return_code} for model {model_name}")
            return "offline"

        try:
            output = stdout.decode('utf-8', errors='ignore')
        except UnicodeDecodeError as e:
            logging.error(f"Error decoding stdout for {model_name}: {e}")
            return "offline"

        if "hls-" in output:
            logging.info(f"Model {model_name}: m3u8 found")
            return "public"
        else:
            logging.info(f"Model {model_name}: m3u8 not found")
            return "offline"
    except FileNotFoundError as e:
        logging.error(f"yt-dlp not found: {e}")
        return "offline"
    except Exception as e:
        logging.error(f"Failed to check status for {model_name}: {e}")
        return "offline"

async def download_stream(model_name, model_url, user_agent):
    try:
        while not terminate_event.is_set():
            start_time = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            output_file_temp = os.path.join(output_dir, f"{model_name}_{start_time}.tmp")

            logging.info(f"Starting download stream for {model_name}. Output file: {output_file_temp}")
            active_models[model_name] = True

            # Убираем слишком агрессивные параметры, увеличиваем таймауты
            # Убираем --abort-on-unavailable-fragment и слишком маленький socket-timeout
            # Даем больше шансов на продолжение потока
            command = [
                '/usr/bin/yt-dlp', model_url,
                '-o', output_file_temp,
                '--user-agent', user_agent,
                '-f', 'bestvideo[height<=720][vbr<=1500k]+bestaudio[abr<=128k]/best[height<=720]',
                '--hls-prefer-ffmpeg',
                '--buffer-size', '16M',
                '--http-chunk-size', '4M',
                '--no-post-overwrites',
                '--retries', '10',
                '--fragment-retries', '10',
                '--skip-unavailable-fragments',
                # Уменьшаем жесткость сетевых параметров
                '--socket-timeout', '30'
            ]

            process = await asyncio.create_subprocess_exec(*command)
            return_code = await process.wait()
            if return_code != 0:
                logging.error(f"yt-dlp exited with code {return_code} for model {model_name}")
                if os.path.exists(output_file_temp):
                    final_output_file = os.path.join(output_dir, f"{model_name}_{start_time}.mp4")
                    try:
                        os.rename(output_file_temp, final_output_file)
                        logging.info(f"File renamed to {final_output_file} after error.")
                    except OSError as e:
                        logging.error(f"Failed to rename file {output_file_temp} to {final_output_file}: {e}")
                break  # Exit if yt-dlp errors out

            logging.info(f"Download completed for {model_name}. Checking for continuation...")

            final_output_file = os.path.join(output_dir, f"{model_name}_{start_time}.mp4")
            try:
                os.rename(output_file_temp, final_output_file)
                logging.info(f"File renamed to {final_output_file}")
            except OSError as e:
                logging.error(f"Failed to rename file {output_file_temp} to {final_output_file}: {e}")

            async with aiohttp.ClientSession() as session:
                model_status = await check_model_status(session, model_name, model_url, user_agent)

            if model_status == "offline" or terminate_event.is_set():
                logging.info(f"Model {model_name} is now offline or termination requested. Stopping recording.")
                break
    except asyncio.CancelledError:
        logging.info(f"Download stream for {model_name} was cancelled.")
    except Exception as e:
        logging.error(f"Error occurred while downloading {model_name} with yt-dlp: {e}")
        if os.path.exists(output_file_temp):
            final_output_file = os.path.join(output_dir, f"{model_name}_{start_time}.mp4")
            try:
                os.rename(output_file_temp, final_output_file)
                logging.info(f"File renamed to {final_output_file} after exception.")
            except OSError as e:
                logging.error(f"Failed to rename file {output_file_temp} to {final_output_file}: {e}")
    finally:
        if model_name in active_models:
            del active_models[model_name]

# Функция для проверки и загрузки моделей
async def check_and_download_model(session, model_name, model_url, user_agent):
    async with semaphore:
        if model_name in active_models:
            logging.info(f"Model {model_name} is already being recorded. Skipping.")
            return

        status = await check_model_status(session, model_name, model_url, user_agent)
        if status == "public" and not terminate_event.is_set():
            task = asyncio.create_task(download_stream(model_name, model_url, user_agent))
            tasks.append(task)

# Функция для параллельной проверки всех моделей
async def check_models(models_df):
    async with aiohttp.ClientSession() as session:
        check_tasks = []
        for _, row in models_df.iterrows():
            model_name = row['model_name']
            model_name = ''.join(e for e in model_name if e.isalnum() or e in ['-', '_'])
            user_agent = generate_random_user_agent()
            model_url = f"{base_url}{model_name}"
            task = asyncio.create_task(check_and_download_model(session, model_name, model_url, user_agent))
            check_tasks.append(task)
        await asyncio.gather(*check_tasks)

# Асинхронная функция завершения активных загрузок
async def shutdown_handler():
    print("Shutting down gracefully...")
    logging.info("Shutting down gracefully...")

    terminate_event.set()

    for task in tasks:
        if not task.done():
            task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    tasks.clear()
    logging.info("All tasks have been cancelled and completed.")

# Функция для удаления дубликатов в CSV файле
def remove_duplicates_in_csv(file_path):
    try:
        df = pd.read_csv(file_path)
        df['model_name'] = df['model_name'].str.lower()
        df.drop_duplicates(subset="model_name", inplace=True)
        df.to_csv(file_path, index=False)
    except pd.errors.EmptyDataError:
        logging.error(f"CSV file is empty: {file_path}")
    except Exception as e:
        logging.error(f"Error removing duplicates in CSV: {e}")

# Проверка наличия новых моделей в CSV файле
def get_new_models():
    logging.info("Loading models from CSV file")
    remove_duplicates_in_csv(csv_file_path)
    try:
        df = pd.read_csv(csv_file_path)
        return df
    except pd.errors.EmptyDataError:
        logging.error(f"CSV file is empty: {csv_file_path}")
        return pd.DataFrame(columns=['model_name'])
    except Exception as e:
        logging.error(f"Error reading CSV file: {e}")
        return pd.DataFrame(columns=['model_name'])

# Основной цикл проверки и записи моделей
async def main_loop():
    while not terminate_event.is_set():
        logging.info("Starting new cycle of model checking and recording")
        models_df = get_new_models()
        if not models_df.empty:
            logging.info(f"Found models: {models_df['model_name'].tolist()}")
            await check_models(models_df)
        else:
            logging.info("No models found in CSV file.")

        for _ in range(60):
            if terminate_event.is_set():
                break
            await asyncio.sleep(1)
        logging.info("Completed one full cycle, waiting for the next cycle...")

if __name__ == "__main__":
    logging.info("Starting main loop")

    loop = asyncio.get_event_loop()

    # Установка обработчиков сигналов
    loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(shutdown_handler()))
    loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(shutdown_handler()))

    try:
        loop.run_until_complete(main_loop())
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(shutdown_handler())
        loop.close()