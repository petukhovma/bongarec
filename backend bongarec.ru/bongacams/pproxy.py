import requests
from fake_useragent import UserAgent

# URL целевой страницы
url = "https://bongamodels.com/profile/minnimia"

# Генерация случайного User-Agent
ua = UserAgent()
headers = {'User-Agent': ua.random}

try:
    # Отправка запроса и вывод только кода ответа
    response = requests.get(url, headers=headers, timeout=10)
    print(response.status_code)  # Вывод только кода ответа

except requests.RequestException as e:
    print(f"Ошибка при запросе страницы: {e}")
