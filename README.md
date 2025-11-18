# Resmî Gazete Scraper

Bu proje her gün Resmî Gazete ana sayfasını tarayıp başlıkları ve linklerini toplar.

- Çıktı: `data/resmigazete_YYYY-MM-DD.json`
- Ek olarak günlük kayıtlar `scrape.db` içindeki `daily_news` tablosuna da yazılır.
- GitHub Actions ile her gün otomatik çalışır ve yeni JSON'u repoya push eder.

## Yerel Çalıştırma

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

python -m pip install --upgrade pip
pip install -r requirements.txt

python -m playwright install --with-deps chromium

python test_scrape.py