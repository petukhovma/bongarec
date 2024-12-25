import requests
from bs4 import BeautifulSoup
import sqlite3

conn = sqlite3.connect('models.db')
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS models
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)''')

# Добавление ников
def add_to_database(name):
    cursor.execute("INSERT INTO models (name) VALUES (?)", (name,))
    conn.commit()

url = "https://bongacams-archiver.com/models/"

# Получение содержимого страницы
response = requests.get(url)
soup = BeautifulSoup(response.content, 'html.parser')

# Находим все ссылки, которые ведут на профиль модели
model_links = soup.find_all('a', href=True)

#Извлечение ников
for link in model_links:
    if "/profile/" in link['href']:
        model_name = link['href'].split('/')[-2]
        print(f"Model found: {model_name}")
        add_to_database(model_name)

conn.close()
