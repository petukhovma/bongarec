import os
from flask import Flask, render_template, request, jsonify, send_from_directory, session, make_response, abort
from flask_compress import Compress
from flask_caching import Cache
import sqlite3
import requests
import logging
import datetime
import random
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.parse

app = Flask(__name__)
API_KEY = 'key'
app.secret_key = 'key'  # Необходим для использования сессий

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')


def increment_video_views(file_code):
    try:
        query = "UPDATE videos SET views = views + 1 WHERE file_code = ?"
        query_database(query, (file_code,), commit=True)
        logger.info(f"Views incremented successfully for file_code={file_code}")
    except sqlite3.Error as e:
        logger.error(f"SQLite error while incrementing views for file_code={file_code}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error while incrementing views for file_code={file_code}: {e}", exc_info=True)

# Для сжатия и кэширования
Compress(app)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

@app.route('/robots.txt')
def robots_txt():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'robots.txt')

@app.route('/sitemap.xml', methods=['GET'])
@cache.cached(timeout=1800)
def sitemap():
    pages = []
    ten_days_ago = (datetime.datetime.now() - datetime.timedelta(days=10)).date().isoformat()

    # Статические страницы
    pages.append({
        'loc': 'https://www.bongarec.com/',
        'changefreq': 'daily',
        'priority': '0.9',
        'lastmod': ten_days_ago
    })
    pages.append({
        'loc': 'https://www.bongarec.com/models',
        'changefreq': 'weekly',
        'priority': '1.0',
        'lastmod': ten_days_ago
    })
    pages.append({
        'loc': 'https://www.bongarec.com/all_videos',
        'changefreq': 'hourly',
        'priority': '0.8',
        'lastmod': ten_days_ago
    })
    pages.append({
        'loc': 'https://www.bongarec.com/categories',
        'changefreq': 'weekly',
        'priority': '0.7',
        'lastmod': ten_days_ago
    })

    # Страницы моделей
    models = query_database("SELECT model_name FROM models")
    for model in models:

        pages.append({
            'loc': f'https://www.bongarec.com/{model[0]}',
            'changefreq': 'weekly',
            'priority': '1.0',
            'lastmod': ten_days_ago
        })

    # Страницы категорий
    categories = ["Молодые", "Взрослые", "Мамочки", "Зрелые", "Худые", "Средний вес", "Полные", "Толстые", "Низкие", "Средний рост", "Высокие", "Средняя грудь", "Большая грудь", "Маленькая грудь", "Огромные груди", "Средняя попа", "Большая попа", "Маленькая попа"]
    for category in categories:
        pages.append({
            'loc': f'https://www.bongarec.com/category/{category}',
            'changefreq': 'weekly',
            'priority': '0.7',
            'lastmod': ten_days_ago
        })

    # Генерация XML
    sitemap_xml = render_template('sitemap_template.xml', pages=pages)

    response = make_response(sitemap_xml)
    response.headers["Content-Type"] = "application/xml"
    return response

# Настройка логирования
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Настройка отдельного логгера для ошибок аватарок
avatar_logger = logging.getLogger('avatar_errors')
avatar_logger.setLevel(logging.ERROR)
avatar_handler = logging.FileHandler('/var/log/avatar_errors.log')
avatar_handler.setLevel(logging.ERROR)
avatar_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
avatar_handler.setFormatter(avatar_formatter)
avatar_logger.addHandler(avatar_handler)

# Настройки для сессии
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=15)
app.config['SESSION_COOKIE_SECURE'] = True  
app.config['SESSION_COOKIE_HTTPONLY'] = True  
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  

# Путь к базе данных через переменную окружения
DB_PATH = os.getenv('DB_PATH', '/var/www/bongarec/models_data.db')

@app.route('/imgavt/<filename>')
def serve_avatar(filename):
    directory = '/var/www/bongarec/imgavt'
    try:
        return send_from_directory(directory, filename)
    except Exception as e:
        avatar_logger.error(f"Error serving avatar {filename}: {e}", exc_info=True)
        abort(404)

def get_videos_paginated(page, per_page):
    offset = (page - 1) * per_page
    query = "SELECT * FROM videos ORDER BY uploaded DESC LIMIT ? OFFSET ?"
    params = [per_page, offset]
    videos = query_database(query, params)
    return [format_video_data(video) for video in videos] if videos else []

@app.template_filter('timedeltaformat')
def timedeltaformat(value):
    try:
        seconds = int(value)
        return str(datetime.timedelta(seconds=seconds))
    except (ValueError, TypeError) as e:
        logger.error(f"Error in timedeltaformat filter: {e}", exc_info=True)
        return "00:00:00"

def extract_model_name(title):
    return title.split()[0].lower()

def query_database(query, params=(), commit=False):
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(query, params)
        if commit:
            conn.commit()
            logger.info(f"Query committed: {query} with params: {params}")
            return None
        else:
            result = cursor.fetchall()
            logger.info(f"Query executed successfully: {query} with params: {params}")
            return result
    except sqlite3.Error as e:
        logger.error(f"SQLite error: {e}. Query: {query} with params: {params}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"General error: {e}. Query: {query} with params: {params}", exc_info=True)
        return None
    finally:
        if conn:
            conn.close()



def fetch_videos(page=1, per_page=100):
    url = f"https://doodapi.com/api/file/list?key={API_KEY}&page={page}&per_page={per_page}"
    try:
        response = requests.get(url)
        data = response.json()
        if data['status'] == 200:
            return data['result']['files']  # Возвращаем список файлов, содержащих информацию о видео, включая просмотры
        else:
            logger.error(f"Error fetching videos: {data['msg']}")
            return []
    except requests.RequestException as e:
        logger.error(f"RequestException while fetching videos: {e}", exc_info=True)
        return []

def get_file_list(page, per_page):
    videos, total_results, total_pages = [], 0, 0
    try:
        result = fetch_videos('file/list', {'per_page': per_page, 'page': page})
        videos = result.get('files', [])
        for video in videos:
            video['length_formatted'] = timedeltaformat(video['length'])
            video['display_title'] = extract_model_name(video['title'])
        total_results = int(result['results_total'])
        total_pages = int(result['total_pages'])
    except Exception as e:
        logger.error(f"Error in get_file_list: {e}", exc_info=True)
    return videos, total_results, total_pages

def format_video_data(video):
    try:
        if len(video) < 11:
            logger.error(f"Unexpected tuple length: {len(video)}. Data: {video}")
            return None

        return {
            'id': video[0],
            'file_code': video[1],
            'download_url': video[2],
            'single_img': video[3],
            'title': video[4],
            'length': video[5],
            'views': video[6],
            'uploaded': video[7],
            'public': video[8],
            'canplay': video[9],
            'model_name': video[10],
            'length_formatted': format_duration(video[5]) if video[5] else "00:00:00",
            'display_title': extract_model_name(video[4])
        }
    except Exception as e:
        logger.error(f"Unexpected error in format_video_data: {e}. Video data: {video}", exc_info=True)
        return None


def get_all_videos(limit=None):
    query = "SELECT * FROM videos ORDER BY uploaded DESC"
    params = []
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)

    all_videos = query_database(query, params)
    return [format_video_data(video) for video in all_videos] if all_videos else []



def search_videos(query, sort_by='uploaded', page=1, per_page=16):
    try:
        query_lower = query.lower()
        allowed_sort_options = {
            'date': 'v.uploaded DESC',
            'popularity': 'v.views DESC',
            'duration': 'v.length DESC'
        }
        sort_option = allowed_sort_options.get(sort_by, 'v.uploaded DESC')
        offset = (page - 1) * per_page

        sql_query = f"""
            SELECT DISTINCT v.*
            FROM videos v
            JOIN models m ON v.model_name = m.model_name
            WHERE LOWER(m.model_name) = ? OR LOWER(m.other_names) LIKE ?
            ORDER BY {sort_option}
            LIMIT ? OFFSET ?
        """
        videos = query_database(sql_query, (query_lower, f"%{query_lower}%", per_page, offset))
        return [format_video_data(video) for video in videos] if videos else []
    except Exception as e:
        logger.error(f"Error in search_videos: {e}", exc_info=True)
        return []



def get_model_info(model_name):
    query = """
        SELECT 
            model_name,        -- 0
            age,               -- 1
            age_category,      -- 2
            height,            -- 3
            height_category,   -- 4
            weight,            -- 5
            weight_category,   -- 6
            breast_size,       -- 7
            butt_size,         -- 8
            avatar_path,       -- 9
            other_names        -- 10
        FROM 
            models 
        WHERE 
            model_name = ?
    """
    model_info = query_database(query, (model_name,))
    if not model_info:
        return None

    # Исключение None и пустых строк
    model_info = list(model_info[0])
    for i in range(len(model_info)):
        if model_info[i] and isinstance(model_info[i], str):
            if model_info[i].strip().lower() in ['неизвестно', '', 'none']:
                model_info[i] = None

    return model_info




def format_duration(seconds):
    try:
        seconds = int(seconds)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        if hours > 0:
            return f"{hours:02}:{minutes:02}:{seconds:02}"
        else:
            return f"{minutes:02}:{seconds:02}"
    except (ValueError, TypeError) as e:
        logger.error(f"Error in format_duration: {e}", exc_info=True)
        return "00:00"

@app.route('/')
def index():
    try:
        # Пагинация
        page = request.args.get('page', 1, type=int)
        per_page = 16
        paginated_videos = get_videos_paginated(page, per_page)

        # кол-во видео
        total_videos_result = query_database("SELECT COUNT(*) FROM videos")
        total_videos = total_videos_result[0][0] if total_videos_result else 0
        total_pages = (total_videos + per_page - 1) // per_page

        visible_page_count = 5
        start_page = max(1, page - visible_page_count // 2)
        end_page = min(total_pages, start_page + visible_page_count - 1)
        start_page = max(1, end_page - visible_page_count + 1)

        # Популярные видео
        time_period = request.args.get('time_period', 'today')
        popular_page = request.args.get('popular_page', 1, type=int)
        popular_per_page = 16
        popular_videos = get_popular_videos(time_period, page=popular_page, per_page=popular_per_page)

        # Получение общего количества популярных видео для пагинации
        total_popular_videos_result = query_database("SELECT COUNT(*) FROM videos")
        total_popular_videos = total_popular_videos_result[0][0] if total_popular_videos_result else 0
        total_popular_pages = (total_popular_videos + popular_per_page - 1) // popular_per_page

        popular_visible_page_count = 5
        popular_start_page = max(1, popular_page - popular_visible_page_count // 2)
        popular_end_page = min(total_popular_pages, popular_start_page + popular_visible_page_count - 1)
        popular_start_page = max(1, popular_end_page - popular_visible_page_count + 1)

        return render_template('index.html',
                               videos=paginated_videos,
                               total_pages=total_pages,
                               current_page=page,
                               start_page=start_page,
                               end_page=end_page,
                               popular_videos=popular_videos,
                               total_popular_pages=total_popular_pages,
                               popular_page=popular_page,
                               popular_start_page=popular_start_page,
                               popular_end_page=popular_end_page,
                               time_period=time_period)
    except Exception as e:
        logger.error(f"Error in index page: {e}", exc_info=True)
        return render_template('error.html', message="Failed to load the homepage videos."), 500





@cache.cached(timeout=300)
def get_popular_videos(time_period='all_time', page=1, per_page=16):
    try:
        if time_period == 'today':
            date_filter = "WHERE date(uploaded) = date('now', 'localtime')"
        elif time_period == 'this_month':
            date_filter = "WHERE strftime('%Y-%m', uploaded) = strftime('%Y-%m', 'now', 'localtime')"
        else:
            date_filter = ""

        offset = (page - 1) * per_page

        query = f"SELECT * FROM videos {date_filter} ORDER BY views DESC LIMIT ? OFFSET ?"
        params = [per_page, offset]
        videos = query_database(query, params)
        return [format_video_data(video) for video in videos] if videos else []
    except Exception as e:
        logger.error(f"Error in get_popular_videos: {e}", exc_info=True)
        return []


@app.route('/models')
def models_page():
    try:
        per_page = 16
        page = request.args.get('page', 1, type=int)

        filters = {
            'age_category': request.args.get('age_category', ''),
            'height_category': request.args.get('height_category', ''),
            'weight_category': request.args.get('weight_category', ''),
            'breast_size': request.args.get('breast_size', ''),
            'butt_size': request.args.get('butt_size', '')
        }

        query_filters = []
        query_params = []

        for column, value in filters.items():
            if value:
                query_filters.append(f"{column} = ?")
                query_params.append(value)

        where_clause = "WHERE " + " AND ".join(query_filters) if query_filters else ""

        offset = (page - 1) * per_page

        total_models_result = query_database(f"SELECT COUNT(*) FROM models {where_clause}", query_params)
        total_models = total_models_result[0][0] if total_models_result else 0

        models = query_database(
            f"""SELECT model_name, age, height, weight, breast_size, butt_size, avatar_path, age_category, height_category, weight_category 
                FROM models {where_clause} LIMIT ? OFFSET ?""",
            query_params + [per_page, offset]
        )

        total_pages = (total_models + per_page - 1) // per_page

        start_page = max(1, page - 2)
        end_page = min(total_pages, page + 2)
        pages = list(range(start_page, end_page + 1))

        model_videos = {}
        for model in models:
            videos = search_videos(model[0])
            if videos:
                model_videos[model[0]] = random.sample(videos, min(len(videos), 2))

        return render_template('models_page.html', models=models, model_videos=model_videos, total_pages=total_pages, current_page=page, pages=pages)
    except Exception as e:
        logger.error(f"Error in models_page: {e}", exc_info=True)
        return render_template('error.html', message="Failed to load the models page."), 500

@app.route('/all_videos')
def all_videos_page():
    try:
        # Получаем параметры фильтрации из запроса
        allowed_sort_options = {'date': 'v.uploaded DESC', 'popularity': 'v.views DESC', 'duration': 'v.length DESC'}
        age_category = request.args.get('age_category', '')
        height_category = request.args.get('height_category', '')
        weight_category = request.args.get('weight_category', '')
        breast_size = request.args.get('breast_size', '')
        butt_size = request.args.get('butt_size', '')
        sort_by = request.args.get('sort_by', 'views')

        # Фильтры
        filters = []
        params = []

        if age_category:
            filters.append("m.age_category = ?")
            params.append(age_category)
        if height_category:
            filters.append("m.height_category = ?")
            params.append(height_category)
        if weight_category:
            filters.append("m.weight_category = ?")
            params.append(weight_category)
        if breast_size:
            filters.append("m.breast_size = ?")
            params.append(breast_size)
        if butt_size:
            filters.append("m.butt_size = ?")
            params.append(butt_size)

        filter_query = " AND ".join(filters) if filters else "1=1"

        # Проверяем значение sort_by и устанавливаем порядок сортировки
        order_by_clause = allowed_sort_options.get(sort_by, 'v.views DESC')

        # Параметры пагинации
        page = request.args.get('page', 1, type=int)
        per_page = 16
        offset = (page - 1) * per_page

        # Запрос общего количества видео
        total_videos_query = f"""
            SELECT COUNT(*) FROM videos v
            JOIN models m ON v.model_name = m.model_name
            WHERE {filter_query}
        """
        total_videos_result = query_database(total_videos_query, params)
        total_videos = total_videos_result[0][0] if total_videos_result else 0
        total_pages = (total_videos + per_page - 1) // per_page

        # **Здесь добавляем v.model_name в SELECT**
        query = f"""
            SELECT v.file_code, v.single_img, v.title, v.uploaded, v.length, v.views, v.model_name FROM videos v
            JOIN models m ON v.model_name = m.model_name
            WHERE {filter_query}
            ORDER BY {order_by_clause}
            LIMIT ? OFFSET ?
        """

        all_videos = query_database(query, params + [per_page, offset])

        if all_videos is None:
            return render_template('error.html', message="Failed to load the videos page due to database query issue."), 500

        videos_info = [
            {
                'file_code': video[0],
                'single_img': video[1],
                'display_title': video[2],
                'uploaded': video[3],
                'length_formatted': format_duration(video[4]),
                'views': video[5],
                'model_name': video[6]  # **Добавили model_name в словарь**
            } for video in all_videos
        ]

        visible_page_count = 5
        start_page = max(1, page - visible_page_count // 2)
        end_page = min(total_pages, start_page + visible_page_count - 1)
        start_page = max(1, end_page - visible_page_count + 1)

        return render_template('all_videos.html',
                               videos=videos_info,
                               total_pages=total_pages,
                               current_page=page,
                               start_page=start_page,
                               end_page=end_page,
                               sort_by=sort_by)
    except Exception as e:
        logger.error(f"Error in all_videos page: {e}", exc_info=True)
        return render_template('error.html', message="Failed to load the videos page due to an unexpected error."), 500



@app.route('/categories')
def categories_page():
    try:
        categories = {
            "Молодые": "age_category",
            "Взрослые": "age_category",
            "Мамочки": "age_category",
            "Зрелые": "age_category",
            "Худые": "weight_category",
            "Средний вес": "weight_category",
            "Полные": "weight_category",
            "Толстые": "weight_category",
            "Низкие": "height_category",
            "Средний рост": "height_category",
            "Высокие": "height_category",
            "Средняя грудь": "breast_size",
            "Большая грудь": "breast_size",
            "Маленькая грудь": "breast_size",
            "Огромные груди": "breast_size",
            "Средняя попа": "butt_size",
            "Большая попа": "butt_size",
            "Маленькая попа": "butt_size"
        }
        categories_with_videos = {}

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        for category_name, column_name in categories.items():
            if column_name in ["breast_size", "butt_size"]:
                search_term = category_name.split()[0]
            else:
                search_term = category_name

            cursor.execute(f"SELECT model_name FROM models WHERE {column_name} = ?", (search_term,))
            model_names = cursor.fetchall()
            model_names = [name[0] for name in model_names]

            if model_names:
                placeholders = ', '.join('?' for _ in model_names)
                title_conditions = ' OR '.join([f'title LIKE ?' for _ in model_names])
                query = f"""
                    SELECT * FROM videos
                    WHERE {title_conditions}
                    ORDER BY RANDOM()
                    LIMIT 8
                """
                cursor.execute(query, [f"%{model_name}%" for model_name in model_names])
                videos = cursor.fetchall()

                if videos:
                    formatted_videos = [format_video_data(video) for video in videos]
                    categories_with_videos[category_name] = formatted_videos
                else:
                    categories_with_videos[category_name] = []
            else:
                categories_with_videos[category_name] = []

        conn.close()

        return render_template('categories_page.html', categories_with_videos=categories_with_videos)
    except Exception as e:
        logger.error(f"Error in categories_page: {e}", exc_info=True)
        return render_template('error.html', message="Failed to load the categories page."), 500

@app.route('/category/<category_name>')
def category_videos_page(category_name):
    try:
        categories = {
            "Молодые": "age_category",
            "Взрослые": "age_category",
            "Мамочки": "age_category",
            "Зрелые": "age_category",
            "Худые": "weight_category",
            "Средний вес": "weight_category",
            "Полные": "weight_category",
            "Толстые": "weight_category",
            "Низкие": "height_category",
            "Средний рост": "height_category",
            "Высокие": "height_category",
            "Средняя грудь": "breast_size",
            "Большая грудь": "breast_size",
            "Маленькая грудь": "breast_size",
            "Огромные груди": "breast_size",
            "Средняя попа": "butt_size",
            "Большая попа": "butt_size",
            "Маленькая попа": "butt_size"
        }

        if category_name not in categories:
            return render_template('error.html', message="Invalid category"), 404

        column_name = categories[category_name]

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        if column_name in ["breast_size", "butt_size"]:
            search_term = category_name.split()[0]
        else:
            search_term = category_name

        cursor.execute(f"SELECT model_name FROM models WHERE {column_name} = ?", (search_term,))
        model_names = cursor.fetchall()
        model_names = [name[0] for name in model_names]

        if model_names:
            title_conditions = ' OR '.join([f'title LIKE ?' for _ in model_names])
            query = f"""
                SELECT * FROM videos
                WHERE {title_conditions}
                ORDER BY uploaded DESC
            """
            cursor.execute(query, [f"%{model_name}%" for model_name in model_names])
            all_videos = cursor.fetchall()
        else:
            all_videos = []

        conn.close()

        page = request.args.get('page', 1, type=int)
        per_page = 16
        total_videos = len(all_videos)
        total_pages = (total_videos + per_page - 1) // per_page

        visible_page_count = 5
        start_page = max(1, page - visible_page_count // 2)
        end_page = min(total_pages, start_page + visible_page_count - 1)
        start_page = max(1, end_page - visible_page_count + 1)

        paginated_videos = all_videos[(page - 1) * per_page:page * per_page]

        formatted_videos = [format_video_data(video) for video in paginated_videos]

        return render_template('category_videos_page.html',
                               category_name=category_name,
                               videos=formatted_videos,
                               total_pages=total_pages,
                               current_page=page,
                               start_page=start_page,
                               end_page=end_page)
    except Exception as e:
        logger.error(f"Error in category_videos_page: {e}", exc_info=True)
        return render_template('error.html', message="Failed to load the category videos page."), 500

def format_model_data(model):
    return {
        'model_name': model[0],
        'age': model[1],
        'age_category': model[2],
        'height': model[3],
        'height_category': model[4],
        'weight': model[5],
        'weight_category': model[6],
        'breast_size': model[7],
        'butt_size': model[8],
        'avatar_path': model[9]
    }


@app.route('/api/videos')
def get_videos():
    page = request.args.get('page', 1, type=int)
    query = request.args.get('query', '', type=str)
    per_page = 16

    videos = search_videos(query) if query else get_all_videos()

    total_videos = len(videos)
    total_pages = (total_videos + per_page - 1) // per_page

    start_page = max(1, page - 2)
    end_page = min(total_pages, page + 2)
    pages = list(range(start_page, end_page + 1))

    paginated_videos = videos[(page - 1) * per_page:page * per_page]

    return jsonify({
        'videos': paginated_videos,
        'total_pages': total_pages,
        'current_page': page,
        'pages': pages
    })

@app.route('/search')
def search_results():
    try:
        query = request.args.get('query', '', type=str)
        page = request.args.get('page', 1, type=int)
        per_page = 16

        # Получаем общее количество подходящих видео
        total_videos_query = """
            SELECT COUNT(DISTINCT v.id)
            FROM videos v
            JOIN models m ON v.model_name = m.model_name
            WHERE LOWER(m.model_name) = ? OR LOWER(m.other_names) LIKE ?
        """
        total_videos_result = query_database(total_videos_query, (query.lower(), f"%{query.lower()}%"))
        total_videos = total_videos_result[0][0] if total_videos_result else 0

        if total_videos == 0:
            return render_template('error.html', message=f"No videos found for query '{query}'"), 404

        total_pages = (total_videos + per_page - 1) // per_page
        offset = (page - 1) * per_page

        # Получаем видео для текущей страницы
        videos = search_videos(query, page=page, per_page=per_page)

        visible_page_count = 5
        start_page = max(1, page - visible_page_count // 2)
        end_page = min(total_pages, start_page + visible_page_count - 1)
        start_page = max(1, end_page - visible_page_count + 1)

        return render_template('search_results.html',
                               videos=videos,
                               query=query,
                               total_pages=total_pages,
                               current_page=page,
                               start_page=start_page,
                               end_page=end_page)
    except Exception as e:
        logger.error(f"Error in search_results: {e}", exc_info=True)
        return render_template('error.html', message="An error occurred during the search."), 500



@app.route('/<model_name>/<file_code>')
def video_page(model_name, file_code):
    return get_video_info_and_related(model_name, file_code, extract_model_name)

@cache.memoize(timeout=300)
def get_video_info(file_code):
    try:
        query = "SELECT * FROM videos WHERE file_code = ?"
        video = query_database(query, (file_code,))
        if not video:
            logger.error(f"No video found with file_code: {file_code}")
            return None
        return format_video_data(video[0])
    except sqlite3.Error as e:
        logger.error(f"SQLite error in get_video_info: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_video_info: {e}", exc_info=True)
        return None

def get_video_info_and_related(model_name, file_code, extract_model_name_func):
    try:
        # Получение информации о видео
        video = get_video_info(file_code)
        if not video:
            return render_template('error.html', message="Failed to load video details"), 404

        # Увеличение количества просмотров
        increment_video_views(file_code)

        # Удаление кэша для обновления просмотров
        cache.delete_memoized(get_video_info, file_code)

        # Повторное получение информации о видео после обновления
        video = get_video_info(file_code)

        # Получение всех видео этой модели
        all_model_videos = search_videos(model_name, per_page=100)  # Получаем до 100 видео модели

        # Исключаем текущее видео из списка и выбираем 8 случайных
        other_model_videos = [vid for vid in all_model_videos if vid['file_code'] != file_code]
        random_model_videos = random.sample(other_model_videos, min(len(other_model_videos), 8)) if other_model_videos else []

        # Получение всех видео для "Recently uploaded videos"
        all_videos = get_all_videos(limit=100)  # Получаем до 100 видео для случайного выбора
        random_all_videos = random.sample(all_videos, min(len(all_videos), 8)) if all_videos else []

        # Получение информации о модели
        model_info = get_model_info(model_name)

        # Форматирование тегов и аватара модели
        tags = []
        avatar_filename = 'nopic.png'

        if model_info:
            if model_info[7]: tags.append(f'Грудь: {model_info[7]}')
            if model_info[8]: tags.append(f'Попа: {model_info[8]}')
            if model_info[2]: tags.append(f'Возраст: {model_info[2]}')
            if model_info[4]: tags.append(f'Рост: {model_info[4]}')
            if model_info[6]: tags.append(f'Вес: {model_info[6]}')

            avatar_filename = model_info[9] if model_info[9] else 'nopic.png'

        tags = ', '.join(tags)

        # Вычисляем общее количество видео для модели
        total_videos_result = query_database(
            "SELECT COUNT(*) FROM videos WHERE LOWER(model_name) = ?",
            (model_name.lower(),)
        )
        video_count = total_videos_result[0][0] if total_videos_result else 0

        return render_template(
            'video_detail.html',
            video=video,
            model_name=model_name,
            random_model_videos=random_model_videos,
            random_all_videos=random_all_videos,
            model_info=model_info,
            avatar_filename=avatar_filename,
            tags=tags,
            extract_model_name=extract_model_name_func,
            video_count=video_count  # Передаем переменную в шаблон
        )
    except Exception as e:
        logger.error(f"Error in get_video_info_and_related: {e}", exc_info=True)
        return render_template('error.html', message="Failed to load video page."), 500




@app.route('/<model_name>')
def model_page(model_name):
    try:
        # Исключения для файлов от конфликом в /models
        if model_name in ['robots.txt', 'favicon.ico', 'yandex_a5b235.html', '585c59428620a73263c52.html']:
            return send_from_directory(app.static_folder, model_name)

        sort_by_param = request.args.get('sort_by', 'date')
        allowed_sort_by = ['date', 'popularity', 'duration']

        if sort_by_param not in allowed_sort_by:
            sort_by_param = 'date'

        page = request.args.get('page', 1, type=int)
        per_page = 16

        model_videos = search_videos(model_name, sort_by=sort_by_param, page=page, per_page=per_page)

        # Получаем общее количество видео для модели
        total_videos_result = query_database(
            "SELECT COUNT(*) FROM videos WHERE LOWER(model_name) = ?",
            (model_name.lower(),)
        )
        total_videos = total_videos_result[0][0] if total_videos_result else 0
        total_pages = (total_videos + per_page - 1) // per_page

        # Параметры для пагинации
        start_page = max(1, page - 2)
        end_page = min(total_pages, page + 2)
        pages = list(range(start_page, end_page + 1))

        # Получаем информацию о модели
        model_info = get_model_info(model_name)

        # Подготовка данных для тегов и аватара
        tags = []
        avatar_filename = 'nopic.png'  # Значение по умолчанию
        other_nicknames = []  # Инициализируем список других ников

        if model_info:
            if model_info[7] and model_info[7].lower() != 'неизвестно':
                tags.append(f'Грудь: {model_info[7]}')
            if model_info[8] and model_info[8].lower() != 'неизвестно':
                tags.append(f'Попа: {model_info[8]}')
            if model_info[2] and model_info[2].lower() != 'неизвестно':
                tags.append(f'Возраст: {model_info[2]}')
            if model_info[4] and model_info[4].lower() != 'неизвестно':
                tags.append(f'Рост: {model_info[4]}')
            if model_info[6] and model_info[6].lower() != 'неизвестно':
                tags.append(f'Вес: {model_info[6]}')

            avatar_filename = model_info[9]
            if not avatar_filename or avatar_filename.strip().lower() in ['none', 'неизвестно']:
                avatar_filename = 'nopic.png'

            if model_info[10]:
                other_names_str = model_info[10]
                other_nicknames_list = [name.strip() for name in other_names_str.split(',')]
                other_nicknames = other_nicknames_list[:4]  # Берем первые 4 ника

        tags = ', '.join(tags)

        # Рендер
        return render_template(
            'model_page.html',
            model_name=model_name,
            videos=model_videos,
            total_pages=total_pages,
            current_page=page,
            pages=pages,
            model_info=model_info,
            video_count=total_videos,  # Передаем общее количество видео
            tags=tags,
            sort_by=sort_by_param,
            avatar_filename=avatar_filename,
            other_nicknames=other_nicknames  # Передаем другие ники в шаблон
        )
    except Exception as e:
        logger.error(f"Error in model_page: {e}", exc_info=True)
        return render_template('error.html', message="Failed to load model page."), 500




@app.route('/tag/<tag_name>')
def tag_page(tag_name):
    try:
        column_map = {
            'возраст': 'age_category',
            'рост': 'height_category',
            'вес': 'weight_category',
            'грудь': 'breast_size',
            'попа': 'butt_size'
        }

        tag_parts = tag_name.split(':', 1)
        if len(tag_parts) == 2:
            category, value = tag_parts
            category = category.strip().lower()
            value = value.strip()
        else:
            return render_template('error.html', message=f"No models found with tag '{tag_name}'"), 404

        column_name = column_map.get(category)
        if not column_name:
            return render_template('error.html', message=f"No models found with tag '{tag_name}'"), 404

        query = f"""
            SELECT 
                model_name, 
                age, 
                height, 
                weight, 
                breast_size, 
                butt_size, 
                avatar_path
            FROM 
                models 
            WHERE 
                {column_name} = ?
        """
        models = query_database(query, (value,))

        if not models:
            return render_template('error.html', message=f"No models found with tag '{tag_name}'"), 404

        model_videos = {}
        for model in models:
            videos = search_videos(model[0], per_page=2)
            if videos:
                model_videos[model[0]] = videos

        return render_template('tag_page.html', tag_name=tag_name, models=models, model_videos=model_videos)
    except Exception as e:
        logger.error(f"Error in tag_page: {e}", exc_info=True)
        return render_template('error.html', message="An error occurred while loading the tag page"), 500


@app.route('/tag/<path:tag_name>/videos')
def tag_videos_page(tag_name):
    try:
        logger.debug(f"Received tag_name (raw): {tag_name}")

        # Decode the URL-encoded tag_name
        tag_name = urllib.parse.unquote(tag_name)
        logger.debug(f"Decoded tag_name: {tag_name}")

        category_map = {
            'возраст': 'age_category',
            'рост': 'height_category',
            'вес': 'weight_category',
            'грудь': 'breast_size',
            'попа': 'butt_size'
        }

        tag_name_lower = tag_name.lower()
        category, value = None, None
        for key in category_map.keys():
            key_with_colon = f"{key}:"
            if tag_name_lower.startswith(key_with_colon):
                category = category_map[key]
                value = tag_name[len(key_with_colon):].strip()
                break

        if category is None or not value:
            return render_template('error.html', message=f"No videos found with tag '{tag_name}'"), 404

        cache_key = f"{category}_{value}_videos"
        cached_videos = cache.get(cache_key)
        if cached_videos:
            videos = cached_videos
        else:
            query = f"SELECT model_name FROM models WHERE {category} = ?"
            models = query_database(query, (value,))
            if not models:
                return render_template('error.html', message=f"No videos found with tag '{tag_name}'"), 404

            model_names = [model[0] for model in models]
            if model_names:
                placeholders = ','.join('?' for _ in model_names)
                sql_query = f"""
                    SELECT * FROM videos
                    WHERE LOWER(model_name) IN ({placeholders})
                    ORDER BY uploaded DESC
                """
                videos_data = query_database(sql_query, [name.lower() for name in model_names])
                videos = [format_video_data(video) for video in videos_data]
            else:
                videos = []

            cache.set(cache_key, videos)

        page = request.args.get('page', 1, type=int)
        per_page = 16
        total_videos = len(videos)
        total_pages = (total_videos + per_page - 1) // per_page
        paginated_videos = videos[(page - 1) * per_page:page * per_page]

        display_tag = tag_name.split(':', 1)[1].strip()

        return render_template('tag_videos_page.html', tag_name=display_tag, videos=paginated_videos,
                               total_pages=total_pages, current_page=page)

    except Exception as e:
        logger.error(f"Error in tag_videos_page: {e}", exc_info=True)
        return render_template('error.html', message="An error occurred while loading the tag videos page"), 500


if __name__ == '__main__':
    app.run(debug=True)