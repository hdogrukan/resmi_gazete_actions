import requests
from bs4 import BeautifulSoup
import json
import datetime
import sqlite3
import os
from dateutil import tz

DB_PATH = "scrape.db"


def get_today_date_str_turkey():
    tz_tr = tz.gettz("Europe/Istanbul")
    now_tr = datetime.datetime.now(tz=tz_tr)
    return now_tr.strftime("%Y-%m-%d")


def scrape_resmigazete():
    url = "https://www.resmigazete.gov.tr/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/127.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    items, seen = [], set()
    for a in soup.find_all("a"):
        title = (a.get_text() or "").strip()
        href = a.get("href")

        if not title or len(title) < 5 or not href:
            continue

        if href.startswith("/"):
            full_url = "https://www.resmigazete.gov.tr" + href
        elif href.startswith("http"):
            full_url = href
        else:
            full_url = "https://www.resmigazete.gov.tr/" + href.lstrip("./")

        key = (title, full_url)
        if key in seen:
            continue
        seen.add(key)

        items.append({"title": title, "url": full_url})

    return items


def init_db(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_str TEXT NOT NULL,
            json_data TEXT NOT NULL,
            record_count INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()


def insert_daily_record(date_str, items, db_path=DB_PATH):
    payload_json = json.dumps(items, ensure_ascii=False, indent=2)
    created_at_iso = datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO daily_news (date_str, json_data, record_count, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (date_str, payload_json, len(items), created_at_iso),
    )
    conn.commit()
    conn.close()


def save_daily_json(date_str, records):
    os.makedirs("data", exist_ok=True)
    out_path = f"data/resmigazete_{date_str}.json"
    payload = {"date": date_str, "count": len(records), "records": records}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return out_path


def main():
    print("[1] scraping...")
    records = scrape_resmigazete()
    date_str = get_today_date_str_turkey()

    print(f"[2] {date_str} için çekilen kayıt sayısı:", len(records))
    for i, r in enumerate(records, start=1):
        print(f"{i}. {r['title']} — {r['url']}")

    print("[3] JSON kaydediliyor...")
    json_path = save_daily_json(date_str, records)
    print(f"    -> {json_path}")

    print("[4] DB init...")
    init_db()

    print("[5] DB insert...")
    insert_daily_record(date_str, records)

    print(f"[6] OK. SQLite dosyası: {DB_PATH}")


if __name__ == "__main__":
    main()