#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import os
from dateutil import tz
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


def get_today_date_str_turkey():
    tr_tz = tz.gettz("Europe/Istanbul")
    now_tr = datetime.datetime.now(tz=tr_tz)
    return now_tr.strftime("%Y-%m-%d")


def scrape_resmigazete():
    url = "https://www.resmigazete.gov.tr/"
    with sync_playwright() as p:
        proxy_conf = None
        proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or os.environ.get("PROXY_SERVER")
        if proxy_url:
            proxy_conf = {"server": proxy_url}
            proxy_user = os.environ.get("PROXY_USERNAME")
            proxy_pass = os.environ.get("PROXY_PASSWORD")
            if proxy_user and proxy_pass:
                proxy_conf["username"] = proxy_user
                proxy_conf["password"] = proxy_pass

        launch_kwargs = {
            "headless": True,
            "args": ["--disable-blink-features=AutomationControlled"],
        }
        if proxy_conf:
            launch_kwargs["proxy"] = proxy_conf

        browser = p.chromium.launch(**launch_kwargs)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/127.0.0.0 Safari/537.36"
            ),
            locale="tr-TR",
            timezone_id="Europe/Istanbul",
            ignore_https_errors=True,
        )
        page = context.new_page()
        page.set_default_navigation_timeout(90_000)
        page.set_default_timeout(30_000)

        try:
            page.goto(url, wait_until="domcontentloaded")
        except PlaywrightTimeout as e:
            print(f"[warn] goto timeout (domcontentloaded): {e}")
            try:
                page.wait_for_selector("body", timeout=10_000)
            except PlaywrightTimeout:
                print("[warn] body gelmedi, kısa tekrar denemesi")
                page.goto(url, wait_until="domcontentloaded", timeout=30_000)

        html = page.content()
        context.close()

    soup = BeautifulSoup(html, "html.parser")

    items = []
    seen = set()

    for a in soup.find_all("a"):
        title = (a.get_text() or "").strip()
        href = a.get("href")

        if not title:
            continue
        if len(title) < 5:
            continue
        if not href:
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


if __name__ == "__main__":
    data = scrape_resmigazete()
    print(f"{get_today_date_str_turkey()} - {len(data)} kayıt")
    for idx, d in enumerate(data, 1):
        print(idx, d["title"], "->", d["url"])
