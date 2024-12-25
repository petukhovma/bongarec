import sqlite3
import requests
from bs4 import BeautifulSoup
import re
import concurrent.futures


def ensure_last_online_column():
    conn = sqlite3.connect('models.db')
    cursor = conn.cursor()

    # Проверка последнего онлайна
    cursor.execute("PRAGMA table_info(models)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'last_online' not in columns:
        cursor.execute("ALTER TABLE models ADD COLUMN last_online TEXT")
        conn.commit()

    conn.close()


# Function to process each model
def process_model(name):
    conn = sqlite3.connect('models.db')
    cursor = conn.cursor()

    url = f'https://ru.bongamodels.com/profile/{name}'
    try:
        response = requests.get(url)
        if response.status_code == 404:
            print(f"Failed to fetch {url}. Status code: 404. Removing {name} from database.")
            cursor.execute("DELETE FROM models WHERE name = ?", (name,))
            conn.commit()
            return
        elif response.status_code != 200:
            print(f"Failed to fetch {url}. Status code: {response.status_code}")
            cursor.execute("DELETE FROM models WHERE name = ?", (name,))
            conn.commit()
            return

        soup = BeautifulSoup(response.text, 'html.parser')

        text_content = soup.get_text(separator='\n')

        # Поиск "Был(-а)"
        lines = text_content.split('\n')
        last_online_line = None
        for line in lines:
            if 'Был(-а)' in line:
                last_online_line = line.strip()
                break

        if last_online_line:
            cursor.execute("UPDATE models SET last_online = ? WHERE name = ?", (last_online_line, name))
            conn.commit()
            print(f"Updated {name} with last online info: {last_online_line}")
        else:
            print(f"'Был(-а)' not found for {name}. Removing from database.")
            cursor.execute("DELETE FROM models WHERE name = ?", (name,))
            conn.commit()

    except Exception as e:
        print(f"An error occurred for {name}: {e}")
        cursor.execute("DELETE FROM models WHERE name = ?", (name,))
        conn.commit()

    conn.close()


def fetch_names():
    conn = sqlite3.connect('models.db')
    cursor = conn.cursor()

    # Fetch all names from the database
    cursor.execute("SELECT name FROM models")
    names = cursor.fetchall()

    # замена на андерскоры
    updated_names = []
    for name_tuple in names:
        original_name = name_tuple[0]
        updated_name = original_name.replace('_', '-')
        if updated_name != original_name:
            cursor.execute("UPDATE models SET name = ? WHERE name = ?", (updated_name, original_name))
            conn.commit()
        updated_names.append(updated_name)

    conn.close()
    return updated_names


def process_models_concurrently():
    updated_names = fetch_names()

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        executor.map(process_model, updated_names)


if __name__ == "__main__":
    ensure_last_online_column()
    process_models_concurrently()
