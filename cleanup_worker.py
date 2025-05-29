import os
import time
from datetime import datetime

FOLDER = "temp_tiles"
MAX_AGE_SECONDS = 3600  # 1 hour

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)

def clean_folder():
    now = time.time()
    deleted_count = 0

    for filename in os.listdir(FOLDER):
        path = os.path.join(FOLDER, filename)
        if os.path.isfile(path):
            age = now - os.path.getmtime(path)
            if age > MAX_AGE_SECONDS:
                try:
                    os.remove(path)
                    deleted_count += 1
                    log(f"🧹 Deleted {filename}")
                except Exception as e:
                    log(f"❌ Error deleting {filename}: {e}")

    if deleted_count == 0:
        log("🟢 No files to delete this cycle.")
    else:
        log(f"✅ Cleanup complete. {deleted_count} file(s) removed.")

while True:
    log("🔁 Starting cleanup cycle...")
    clean_folder()
    log("😴 Sleeping for 1 hour...\n")
    time.sleep(3600)
