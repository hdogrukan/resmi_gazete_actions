import os
import json
import datetime
from dateutil import tz
from bs4 import BeautifulSoup
from firecrawl import Firecrawl


def get_today_date_str_turkey():
    tz_tr = tz.gettz("Europe/Istanbul")
    now_tr = datetime.datetime.now(tz=tz_tr)
    return now_tr.strftime("%Y-%m-%d")


def get_firecrawl_client():
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        raise RuntimeError(
            "FIRECRAWL_API_KEY environment variable is not set. "
            "Set your Firecrawl API key before running this script."
        )
    return Firecrawl(api_key=api_key)


def scrape_resmigazete_firecrawl():
    url = "https://www.resmigazete.gov.tr/"
    client = get_firecrawl_client()

    # Single-page scrape via Firecrawl (v2).
    doc = client.scrape(url, formats=["html", "rawHtml"])
    html = doc.html or doc.raw_html
    if not html:
        raise RuntimeError("Firecrawl did not return HTML content for the page.")

    soup = BeautifulSoup(html, "html.parser")

    # Ana sayfadaki kategori başlıklarını (html-title, html-subtitle) linklerle eşleştir
    category_map = {}
    content_div = soup.find("div", id="html-content")
    if content_div:
        current_html_title = None
        current_html_subtitle = None

        for child in content_div.children:
            # Sadece tag olan çocukları işle (string vs. atla)
            if not getattr(child, "get", None):
                continue

            classes = child.get("class", []) or []

            if "card-title" in classes and "html-title" in classes:
                # Örn: "YÜRÜTME VE İDARE BÖLÜMÜ", "İLÂN BÖLÜMÜ"
                current_html_title = (child.get_text() or "").strip()
                current_html_subtitle = None
                continue

            if "html-subtitle" in classes:
                # Örn: "YÖNETMELİKLER", "KURUL KARARLARI"
                current_html_subtitle = (child.get_text() or "").strip()
                continue

            if "fihrist-item" in classes:
                a_tag = child.find("a", href=True)
                if not a_tag:
                    continue

                href = a_tag["href"]
                if href.startswith("/"):
                    full_url = "https://www.resmigazete.gov.tr" + href
                elif href.startswith("http"):
                    full_url = href
                else:
                    full_url = "https://www.resmigazete.gov.tr/" + href.lstrip("./")

                category_map[full_url] = {
                    "html_title": current_html_title,
                    "html_subtitle": current_html_subtitle,
                }

    items = []
    seen = set()

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

        item = {"title": title, "url": full_url}

        # Eğer bu URL html-content içindeki fihrist-item altında ise
        # ona ait html başlık / alt başlık bilgilerini de ekle
        cat_info = category_map.get(full_url)
        if cat_info:
            if cat_info.get("html_title"):
                item["html_title"] = cat_info["html_title"]
            if cat_info.get("html_subtitle"):
                item["html_subtitle"] = cat_info["html_subtitle"]

        items.append(item)

    # Her bir HTML sayfasındaki class="html-content" içeriğini de ekle
    for item in items:
        item_url = item["url"]

        # Sadece HTML sayfalar için (ör. .htm / .html) içerik çek
        if not item_url.startswith("https://www.resmigazete.gov.tr"):
            continue
        if not (item_url.endswith(".htm") or item_url.endswith(".html")):
            continue

        try:
            detail_doc = client.scrape(item_url, formats=["html", "rawHtml"])
        except Exception as e:
            print(f"[warn] Firecrawl detail scrape failed for {item_url}: {e}")
            continue

        detail_html = detail_doc.html or detail_doc.raw_html
        if not detail_html:
            continue

        detail_soup = BeautifulSoup(detail_html, "html.parser")
        content_nodes = detail_soup.find_all(class_="html-content")
        if not content_nodes:
            continue

        html_parts = [str(node) for node in content_nodes]
        text_parts = [
            node.get_text("\n", strip=True)
            for node in content_nodes
            if (node.get_text() or "").strip()
        ]

        if html_parts:
            item["html_content"] = "\n\n".join(html_parts)
        if text_parts:
            item["html_content_text"] = "\n\n".join(text_parts)

    return items


def build_tree(records):
    """
    Kayıtları aşağıdaki gibi ağaç yapısına dönüştürür:
    [
      {
        "html_title": "...",
        "subtitles": [
          {
            "html_subtitle": "...",
            "items": [
              {"title": "...", "url": "..."},
              ...
            ]
          },
          ...
        ]
      },
      ...
    ]
    """
    tree_dict = {}

    for rec in records:
        html_title = rec.get("html_title")
        if not html_title:
            # Sadece gunluk-akis içindeki fihrist-item kayıtlarını ağaçta göster
            continue
        html_subtitle = rec.get("html_subtitle")

        tree_dict.setdefault(html_title, {})
        tree_dict[html_title].setdefault(html_subtitle, [])

        tree_dict[html_title][html_subtitle].append(
            {
                "title": rec.get("title"),
                "url": rec.get("url"),
            }
        )

    tree = []
    for html_title, subtitle_map in tree_dict.items():
        subtitles = []
        for html_subtitle, items in subtitle_map.items():
            subtitles.append(
                {
                    "html_subtitle": html_subtitle,
                    "items": items,
                }
            )
        tree.append(
            {
                "html_title": html_title,
                "subtitles": subtitles,
            }
        )

    return tree


def count_tree_items(tree):
    total = 0
    for section in tree:
        for subtitle in section.get("subtitles", []):
            total += len(subtitle.get("items", []))
    return total


def save_daily_json(date_str, records):
    os.makedirs("data", exist_ok=True)
    out_path = f"data/resmigazete_{date_str}.json"
    tree = build_tree(records)
    payload = {
        "date": date_str,
        "count": count_tree_items(tree),
        "tree": tree,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return out_path


def main():
    print("[1] Firecrawl ile scraping...")
    records = scrape_resmigazete_firecrawl()
    date_str = get_today_date_str_turkey()

    print(f"[2] {date_str} için çekilen kayıt sayısı:", len(records))
    for i, r in enumerate(records, start=1):
        print(f"{i}. {r['title']} — {r['url']}")

    print("[3] JSON kaydediliyor...")
    json_path = save_daily_json(date_str, records)
    print(f"    -> {json_path}")

    print("[4] Tamamlandı.")


if __name__ == "__main__":
    main()
