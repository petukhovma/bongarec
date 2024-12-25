import pandas as pd
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from fake_useragent import UserAgent

ua = UserAgent()

input_file = 'model_nicks.txt'
df = pd.read_csv(input_file, header=None, names=['name'])
df['followers'] = None

base_url = "https://ru.bongacams.xxx/profile/"


# Получение количества подписчиков
def get_follower_count(model_name):
    profile_url = f"{base_url}{model_name}"
    headers = {"User-Agent": ua.random}  # Устанавливаем случайный User-Agent
    try:
        response = requests.get(profile_url, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        follower_span = soup.find('span', class_='js-flwr_cnt')
        if follower_span:
            follower_count = follower_span.get('data-count')
            print(f"Для модели {model_name} найдено количество подписчиков: {follower_count}")
            return follower_count
        else:
            print(f"Не удалось найти количество подписчиков для модели {model_name}")
            return "N/A"
    except Exception as e:
        print(f"Ошибка при обработке модели {model_name}: {e}")
        return "Error"


# Обработка каждой модели
def process_model(row):
    model_name = row['name']
    if pd.notna(row.get('followers')) and row['followers'] != "N/A" and row['followers'] != "Error":
        print(f"Количество подписчиков для модели {model_name} уже существует, пропуск")
        return row['followers']

    return get_follower_count(model_name)


with ThreadPoolExecutor(max_workers=4) as executor:
    futures = {executor.submit(process_model, row): row['name'] for _, row in df.iterrows()}

    for future in as_completed(futures):
        model_name = futures[future]
        try:
            followers = future.result()
            df.loc[df['name'] == model_name, 'followers'] = followers
        except Exception as e:
            print(f"Ошибка при обработке модели {model_name}: {e}")

output_file = 'models_with_followers.xlsx'
df.to_excel(output_file, index=False, engine='openpyxl')

print(f"Данные сохранены в {output_file}")
