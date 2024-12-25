import asyncio
import pandas as pd

# Загрузите файл CSV
file_path = 'models.csv'
models_df = pd.read_csv(file_path)

async def check_model(model_name):
    url = f"https://ru4.bongacams.com/{model_name}"
    command = f'yt-dlp --user-agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:79.0) Gecko/20100101 Firefox/79.0" --get-url "{url}"'

    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            # Команда выполнена успешно
            print(f"Model {model_name} is online. Stream URL: {stdout.decode().strip()}")
        else:
            # Ошибка при выполнении команды
            print(f"Model {model_name} is offline or URL is not available.")
    except Exception as e:
        # Обработка исключений
        print(f"Failed to check status for model {model_name}: {e}")

async def main():
    tasks = [check_model(row['model_name']) for _, row in models_df.iterrows()]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
