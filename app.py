from pathlib import Path
from threading import Lock, Thread
from time import sleep

from flask import Flask, jsonify, send_from_directory
from scraper import load_scrape_meta, run_scrape_cycle

app = Flask(__name__, static_folder=".")
BASE_DIR = Path(__file__).resolve().parent
SCRAPE_INTERVAL_SECONDS = 15 * 60
_scrape_lock = Lock()


def scrape_worker() -> None:
    while True:
        try:
            with _scrape_lock:
                run_scrape_cycle()
        except Exception as exc:
            print(f"Auto-scrape failed: {exc}")
        sleep(SCRAPE_INTERVAL_SECONDS)


@app.get("/")
def root():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/favicon.svg")
def favicon():
    return send_from_directory(BASE_DIR, "favicon.svg")


@app.get("/deals.json")
def deals():
    deals_file = BASE_DIR / "deals.json"
    if deals_file.exists():
        return send_from_directory(BASE_DIR, "deals.json")
    return jsonify([])


@app.get("/scrape-status")
def scrape_status():
    return jsonify(load_scrape_meta())


def start_background_scraper() -> None:
    t = Thread(target=scrape_worker, daemon=True)
    t.start()


start_background_scraper()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
