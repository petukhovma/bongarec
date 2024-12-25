import requests
from bs4 import BeautifulSoup
import sqlite3
import concurrent.futures
import time

# Подключение к базе данных
conn = sqlite3.connect('models_data.db')
cursor = conn.cursor()

# Проверка наличия столбца 'othernicks', добавление его, если он отсутствует
def check_and_add_column():
    cursor.execute("PRAGMA table_info(models)")
    columns = cursor.fetchall()
    
    # Проверяем, есть ли столбец othernicks в таблице models
    column_names = [col[1] for col in columns]
    if 'othernicks' not in column_names:
        print("Столбец 'othernicks' не найден. Создаем столбец...")
        cursor.execute("ALTER TABLE models ADD COLUMN othernicks TEXT")
        conn.commit()
        print("Столбец 'othernicks' успешно добавлен.")

# Функция для парсинга страницы модели
def parse_model_page(model_name):
    url = f"https://web2sex.com/models/{model_name}.html"
    try:
        response = requests.get(url)
        
        # Обработка ошибки 429 (слишком много запросов)
        if response.status_code == 429:
            print("Ошибка 429: слишком много запросов. Попробуйте позже.")
            return model_name, None, []
        
        if response.status_code != 200:
            print(f"Страница для {model_name} не найдена.")
            return model_name, None, []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Парсинг никнейма из заголовка, учитываем все возможные префиксы
        header = soup.find('h2', class_='info-title')
        if header:
            nickname = header.text
            # Убираем возможные префиксы
            for prefix in ['Details of', 'Biography of', 'Informations about']:
                if nickname.startswith(prefix):
                    nickname = nickname.replace(prefix, '').strip()
        else:
            nickname = ''
        
        # Парсинг других имен, обрабатываем различные варианты текста
        names_paragraph = soup.find('p', class_='knows-as')
        other_names = []
        
        if names_paragraph:
            other_names_text = names_paragraph.text
            
            # Убираем возможные префиксы: "Known as:", "Other nicknames:", "Other names:"
            for prefix in ['Known as:', 'Other nicknames:', 'Other names:']:
                if other_names_text.startswith(prefix):
                    other_names_text = other_names_text.replace(prefix, '').strip()
            
            # Разделяем имена и удаляем возможные пробелы
            other_names = [name.strip() for name in other_names_text.split(',') if name.strip() and name.strip() != model_name]
        
        return model_name, nickname, other_names
    
    except requests.RequestException as e:
        print(f"Ошибка при запросе модели {model_name}: {e}")
        return model_name, None, []

# Функция для удаления всех префиксов перед записью в базу данных
def clean_nicknames(nicknames):
    cleaned_nicknames = []
    # Убираем любые префиксы (можно добавить свои если нужно)
    prefixes_to_remove = ['Known as:', 'Other nicknames:', 'Other names:', '-']
    for nick in nicknames:
        for prefix in prefixes_to_remove:
            if nick.startswith(prefix):
                nick = nick.replace(prefix, '').strip()
        cleaned_nicknames.append(nick)
    return cleaned_nicknames

# Функция для обновления данных в базе данных
def update_model_nicknames(model_name, nicknames):
    # Чистим ники перед сохранением
    cleaned_nicknames = clean_nicknames(nicknames)
    
    # Объединяем все ники в одну строку, разделенную запятой
    nicknames_str = ', '.join(cleaned_nicknames)
    
    # Обновляем столбец othernicks для конкретной модели
    cursor.execute("""
        UPDATE models
        SET othernicks = ?
        WHERE model_name = ?
    """, (nicknames_str, model_name))
    conn.commit()

# Основная логика скрипта
check_and_add_column()  # Проверяем наличие столбца и добавляем его, если необходимо

# Получаем все имена моделей из базы данных
cursor.execute("SELECT model_name FROM models")
models = cursor.fetchall()

# Пример обработки моделей одновременно (по 10 запросов за раз)
def process_models_concurrently(models):
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(parse_model_page, model[0]) for model in models]
        for future in concurrent.futures.as_completed(futures):
            model_name, nickname, other_names = future.result()
            if nickname:
                print(f"Никнейм: {nickname}")
            else:
                print(f"Никнейм для {model_name} не найден.")
            
            if other_names:
                print(f"Другие имена: {', '.join(other_names)}")
                # Если другие имена найдены, обновляем их в базе данных
                update_model_nicknames(model_name, other_names)
            else:
                print(f"Другие имена для {model_name} не найдены.")

# Запуск обработки моделей
process_models_concurrently(models)

# Закрытие соединения с базой данных
conn.close()
