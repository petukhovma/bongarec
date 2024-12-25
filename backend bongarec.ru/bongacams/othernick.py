import requests
from bs4 import BeautifulSoup
import pandas as pd
import sqlite3
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import os
import time

# Настройка логирования
log_filename = '/var/www/zapisi-bongacams.ru/logs/models_data.log'
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

file_handler = logging.FileHandler(log_filename)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(console_handler)

db_path = '/var/www/zapisi-bongacams.ru/models_data.db'

def create_database_and_tables():
    """Создание базы данных и таблиц."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_code TEXT UNIQUE,
            download_url TEXT,
            single_img TEXT,
            title TEXT,
            length INTEGER,
            views INTEGER DEFAULT 0,
            uploaded DATETIME,
            public INTEGER,
            canplay INTEGER,
            local_views INTEGER DEFAULT 0
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS models (
            model_name TEXT PRIMARY KEY,
            age INTEGER,
            age_category TEXT,
            height TEXT,
            height_category TEXT,
            weight TEXT,
            weight_category TEXT,
            breast_size TEXT,
            butt_size TEXT,
            avatar_path TEXT,
            about_me TEXT,
            other_names TEXT
        );
        """)

        conn.commit()
        logging.info("База данных и таблицы созданы.")
    except sqlite3.Error as e:
        logging.error(f"Ошибка при создании базы данных или таблиц: {e}")
    finally:
        if conn:
            conn.close()

def fetch_videos_from_doodstream(page=1, per_page=200):
    """Получение данных о видео с Doodstream."""
    API_KEY = '431006zwb331iiv350k9c4'
    url = f"https://doodapi.com/api/file/list?key={API_KEY}&page={page}&per_page={per_page}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if data['status'] == 200:
            logging.debug(f"Получены данные о видео с Doodstream: {data}")
            return data['result']['files'], data['result']['total_pages']
        else:
            logging.error(f"Ошибка при получении данных с Doodstream: {data.get('message', 'Неизвестная ошибка')}")
            return [], 0
    except requests.RequestException as e:
        logging.error(f"Ошибка при запросе к Doodstream: {e}")
        return [], 0

def save_videos_to_db(videos):
    """Сохранение данных о видео в базу данных."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        for video in videos:
            cursor.execute("SELECT local_views FROM videos WHERE file_code = ?", (video['file_code'],))
            result = cursor.fetchone()

            if result is not None:
                local_views = result[0]
            else:
                local_views = 0

            cursor.execute("""
                INSERT OR REPLACE INTO videos 
                (file_code, download_url, single_img, title, length, uploaded, public, canplay, local_views) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                video['file_code'],
                video['download_url'],
                video['single_img'],
                video['title'],
                video['length'],
                video['uploaded'],
                video['public'],
                video['canplay'],
                local_views
            ))

        conn.commit()
        logging.info("Данные о видео успешно сохранены в базу данных.")
    except sqlite3.Error as e:
        logging.error(f"Ошибка при сохранении видео в базу данных: {e}")
    finally:
        if conn:
            conn.close()

def load_initial_videos():
    """Первоначальная загрузка данных о видео с Doodstream."""
    page = 1
    per_page = 200
    total_pages = 1

    while page <= total_pages:
        logging.info(f"Загрузка видео с Doodstream: страница {page} из {total_pages}")
        videos, total_pages = fetch_videos_from_doodstream(page, per_page)
        save_videos_to_db(videos)
        page += 1
    logging.info("Первоначальная загрузка видео завершена.")

def model_exists(cursor, model_name):
    """Проверка, существует ли модель в базе данных."""
    cursor.execute("SELECT 1 FROM models WHERE model_name=?", (model_name,))
    return cursor.fetchone() is not None

def categorize_age(age):
    """Категоризация возраста."""
    if age < 25:
        return 'Молодые'
    elif 25 <= age <= 30:
        return 'Взрослые'
    elif 36 <= age <= 44:
        return 'Мамочки'
    else:
        return 'Зрелые'

def extract_average(text, unit='cm'):
    """Извлечение среднего значения из диапазона."""
    if unit == 'cm':
        match = re.search(r'(\d+)\s*см\s*-\s*(\d+)\s*см', text)
    elif unit == 'kg':
        match = re.search(r'(\d+)\s*-\s*(\d+)\s*кг', text)
    elif unit == 'lbs':
        match = re.search(r'(\d+)\s*-\s*(\d+)\s*фунтов', text)

    if match:
        min_value = int(match.group(1))
        max_value = int(match.group(2))
        return (min_value + max_value) / 2

    return None

def categorize_weight(weight_text):
    """Категоризация веса."""
    avg_weight = extract_average(weight_text, unit='kg')
    if avg_weight is None:
        avg_weight = extract_average(weight_text, unit='lbs')
        if avg_weight is not None:
            avg_weight = avg_weight * 0.453592

    if avg_weight is not None:
        if avg_weight < 55:
            return 'Худые'
        elif 56 <= avg_weight <= 60:
            return 'Средний вес'
        elif 61 <= avg_weight <= 70:
            return 'Полные'
        else:
            return 'Толстые'
    return 'Нет'

def categorize_height(height_text):
    """Категоризация роста."""
    avg_height = extract_average(height_text, unit='cm')
    if avg_height is None:
        match = re.search(r'(\d+)\s*\'\s*(\d+)\s*\"', height_text)
        if match:
            feet = int(match.group(1))
            inches = int(match.group(2))
            avg_height = (feet * 30.48) + (inches * 2.54)

    if avg_height is not None:
        if avg_height < 150:
            return 'Низкие'
        elif 150 <= avg_height <= 160:
            return 'Низкие'
        elif 160 < avg_height <= 170:
            return 'Средний рост'
        else:
            return 'Высокие'
    return 'Нет'

def scrape_model_data(model_name):
    """Парсинг данных о модели и сохранение в базу данных."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        if model_exists(cursor, model_name):
            logging.info(f"Модель {model_name} уже существует в базе данных.")
            conn.close()
            return

        url = f'https://ru.bongamodels.com/profile/{model_name}'
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        age = height = weight = breast_size = butt_size = about_me = 'Нет'
        avatar_path = 'Нет'
        age_category = height_category = weight_category = 'Нет'

        age_tag = soup.find(string='Возраст')
        if age_tag:
            age = int(age_tag.find_next().text.split()[0])
            age_category = categorize_age(age)

        height_tag = soup.find(string='Рост')
        if height_tag:
            height = height_tag.find_next().text.strip()
            height_category = categorize_height(height)

        weight_tag = soup.find(string='Вес')
        if weight_tag:
            weight = weight_tag.find_next().text.strip()
            weight_category = categorize_weight(weight)

        breast_size_tag = soup.find(string='Размер груди')
        if breast_size_tag:
            breast_size = breast_size_tag.find_next().text.strip()
        butt_size_tag = soup.find(string='Попа')
        if butt_size_tag:
            butt_size = butt_size_tag.find_next().text.strip()

        about_me_element = soup.find('div', class_='main_block profile_about_details')
        if about_me_element:
            about_me_text = about_me_element.get_text(separator='\n').strip()
            if "Обо мне" in about_me_text:
                about_me = about_me_text.split("Обо мне")[1].split("Меня отталкивает")[0].strip()
            elif "О нас" in about_me_text:
                about_me = about_me_text.split("О нас")[1].split("Меня отталкивает")[0].strip()
            logging.info(f"Полный текст 'about_me' для модели {model_name}: {about_me}")

        avatar_img_tag = soup.find('img', class_='pp_img small_profile_image')
        if avatar_img_tag:
            avatar_url = f"https:{avatar_img_tag['src']}"
            avatar_path = f'{model_name}.jpg'
            avatar_img_data = requests.get(avatar_url).content
            imgavt_dir = '/var/www/zapisi-bongacams.ru/imgavt'
            if not os.path.exists(imgavt_dir):
                os.makedirs(imgavt_dir)
            with open(os.path.join(imgavt_dir, avatar_path), 'wb') as file:
                file.write(avatar_img_data)

        cursor.execute("""
        INSERT OR REPLACE INTO models (model_name, age, age_category, height, height_category, weight, weight_category, breast_size, butt_size, avatar_path, about_me)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            model_name,
            age,
            age_category,
            height,
            height_category,
            weight,
            weight_category,
            breast_size,
            butt_size,
            os.path.join(imgavt_dir, avatar_path),
            about_me
        ))

        conn.commit()
        logging.info(f"Модель {model_name} была успешно сохранена в базе данных.")
    except requests.RequestException as e:
        logging.error(f"Ошибка при запросе к веб-сайту модели {model_name}: {e}")
    except sqlite3.Error as e:
        logging.error(f"Ошибка при сохранении данных модели {model_name} в базу данных: {e}")
    except Exception as e:
        logging.error(f"Ошибка при обработке модели {model_name}: {e}")
    finally:
        if conn:
            conn.close()

def scrape_all_models():
    """Парсинг всех моделей из базы данных."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT DISTINCT model_name FROM models")
        model_names = [row[0] for row in cursor.fetchall()]
        conn.close()

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(scrape_model_data, model_name) for model_name in model_names]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logging.error(f"Ошибка при выполнении задачи: {e}")

        logging.info("Парсинг и сохранение данных о моделях завершены.")
    except sqlite3.Error as e:
        logging.error(f"Ошибка при запуске парсинга всех моделей: {e}")

if __name__ == "__main__":
    create_database_and_tables()
    load_initial_videos()
    
    while True:
        logging.info("Запуск обновления данных...")
        scrape_all_models()
        logging.info("Ожидание 5 минут перед следующим обновлением.")
        time.sleep(300)
