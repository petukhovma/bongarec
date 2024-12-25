# Project Scripts: Model Data Processing and Management

This project includes a series of Python scripts designed to scrape, process, and manage data about models from various websites. Below is a detailed description of each script, its purpose, and how to use it.

## 1. `follower_parser.py`

### Purpose:
Fetches follower counts for a list of models and saves the data to an Excel file.

### How It Works:
- Reads a list of model names from a `model_nicks.txt` file.
- Scrapes the follower count for each model from the Bongacams website.
- Stores the result in an Excel file named `models_with_followers.xlsx`.

### Usage:
1. Prepare a text file `model_nicks.txt` with model names (one per line).
2. Run the script: `python follower_parser.py`.
3. Check the `models_with_followers.xlsx` file for the results.

---

## 2. `nicknames_updater.py`

### Purpose:
Fetches additional nicknames for models and updates the database.

### How It Works:
- Connects to the `models.db` SQLite database.
- Scrapes nicknames from `web2sex.com` for each model.
- Adds or updates the `othernicks` column in the database.

### Usage:
1. Ensure the `models.db` database exists and contains a `models` table.
2. Run the script: `python nicknames_updater.py`.
3. The `othernicks` column in the database will be updated with additional nicknames.

---

## 3. `export_sorted_models.py`

### Purpose:
Exports a sorted list of models from the database to an Excel file.

### How It Works:
- Connects to the `models_sorted.db` SQLite database.
- Fetches models sorted by their last online time.
- Exports the sorted data to an Excel file named `models_sorted.xlsx`.

### Usage:
1. Ensure the `models_sorted.db` database exists.
2. Run the script: `python export_sorted_models.py`.
3. Check the `models_sorted.xlsx` file for the results.

---

## 4. `models_scraper.py`

### Purpose:
Scrapes a list of models from a website and stores them in the database.

### How It Works:
- Fetches model names from `bongacams-archiver.com`.
- Saves the names to the `models` table in the `models.db` database.

### Usage:
1. Ensure the `models.db` database exists.
2. Run the script: `python models_scraper.py`.
3. The `models` table will be populated with the scraped model names.

---

## 5. `last_online_updater.py`

### Purpose:
Updates the last online status of models in the database.

### How It Works:
- Connects to the `models.db` SQLite database.
- Scrapes the last online status for each model from `bongamodels.com`.
- Updates the `last_online` column in the database.
- Removes models that are inactive or no longer exist.

### Usage:
1. Ensure the `models.db` database exists and contains a `models` table.
2. Run the script: `python last_online_updater.py`.
3. The `last_online` column in the database will be updated.

---

## General Notes
- Ensure all dependencies are installed before running the scripts. Install them using:
  ```bash
  pip install -r requirements.txt
  ```
  
- If using these scripts for the first time, set up the databases and required tables as described in the script documentation.

---

## Dependencies
- `pandas`
- `requests`
- `BeautifulSoup` from `bs4`
- `sqlite3`
- `openpyxl`
- `concurrent.futures`
- `fake_useragent`

---

## License
This project is licensed under the terms specified in the repository.
