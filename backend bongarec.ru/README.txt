Script: recordslinux.py
Purpose
- Automatically detects and records public live streams from BongaCams.
- Saves recorded streams in a specified directory.
- Generates detailed logs for each session.

Features
- Checks the online status of models and starts recording if live.
- Saves streams with specific quality settings.
- Handles shutdowns and errors gracefully.

---

Script: uploadlinux.py
Purpose
- Automates the upload of recorded videos to an external hosting platform.
- Continuously monitors a directory for new video files and uploads them once ready.

Features
- Verifies files are complete before uploading.
- Handles retries for failed uploads.
- Deletes temporary files to save storage.
- Supports concurrent uploads.

---

Script: othernick.py
Purpose
- Manages a database of models and videos.
- Scrapes model profiles to collect detailed information, including personal attributes.
- Categorizes models based on parameters such as age, height, and weight.
- Updates the database with new video and model information.

Features
- Collects and stores model data in a structured SQLite database.
- Downloads and saves model avatars locally.
- Fetches video metadata and integrates it into the database.

---

Logs
- Each script generates log files for debugging and tracking purposes. These logs are stored in their respective directories.

---

Disclaimer
- These scripts are for educational and personal use only. Please ensure compliance with the terms of service of the platforms involved and any applicable laws.
