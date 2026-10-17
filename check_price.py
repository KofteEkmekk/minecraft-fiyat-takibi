import json
import os
import sys

import requests

PRODUCT_ID = "9NXP44L49SHJ"  # Minecraft: Java & Bedrock Edition for PC
MARKET = "TR"
LANG = "tr-TR"
API = (
    "https://displaycatalog.mp.microsoft.com/v7.0/products"
    f"?bigIds={PRODUCT_ID}&market={MARKET}&languages={LANG}"
)
STORE_LINK = f"https://www.microsoft.com/tr-tr/p/minecraft-java-bedrock-edition-for-pc/{PRODUCT_ID.lower()}"
STATE_FILE = "price_state.json"

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
# Istege bagli: bu tutarin ALTINA (veya esitine) dusunce de bildir. Bos birakilirsa sadece indirimde bildirir.
TARGET_PRICE = os.environ.get("TARGET_PRICE", "").strip()


def parse_prices(data):
    """Katalog yanitindan satin alinabilir fiyatlari (list, msrp, para birimi) cikarir."""
    found = []
    for product in data.get("Products", []):
        for sku in product.get("DisplaySkuAvailabilities", []):
            for av in sku.get("Availabilities", []):
                actions = av.get("Actions", [])
                price = (av.get("OrderManagementData") or {}).get("Price") or {}
                if "Purchase" not in actions or "ListPrice" not in price:
                    continue
                found.append(
                    {
                        "list": float(price["ListPrice"]),
                        "msrp": float(price.get("MSRP", price["ListPrice"])),
                        "currency": price.get("CurrencyCode", ""),
                    }
                )
    return found


def get_price():
    r = requests.get(API, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    prices = parse_prices(r.json())
    if not prices:
        raise RuntimeError("Fiyat bulunamadi (yanit yapisi degismis olabilir).")
    print("Bulunan fiyatlar:", prices, flush=True)
    # birden fazla secenek varsa en dusuk fiyatliyi al
    return min(prices, key=lambda p: p["list"])


def send(text):
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text},
        timeout=30,
    )
    r.raise_for_status()


def fmt(p):
    return f"{p['list']:.2f} {p['currency']}"


def main():
    p = get_price()
    state = {}
    first_run = not os.path.exists(STATE_FILE)
    if not first_run:
        with open(STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)

    last_price = state.get("last_price")
    notified = state.get("notified_price")

    if first_run:
        send(
            "✅ Minecraft fiyat takibi başladı.\n"
            f"Güncel fiyat: {fmt(p)} (normal fiyat: {p['msrp']:.2f} {p['currency']})\n{STORE_LINK}"
        )
    else:
        on_sale = p["list"] < p["msrp"]
        below_target = bool(TARGET_PRICE) and p["list"] <= float(TARGET_PRICE)
        dropped = last_price is not None and p["list"] < last_price
        if (on_sale or below_target or dropped) and notified != p["list"]:
            send(
                "🎮 Minecraft Java & Bedrock fiyatı düştü!\n"
                f"Şimdi: {fmt(p)}\nNormal fiyat: {p['msrp']:.2f} {p['currency']}\n{STORE_LINK}"
            )
            notified = p["list"]
        elif not (on_sale or below_target or dropped):
            notified = None  # indirim bitti, bir sonrakinde tekrar bildir

    state = {"last_price": p["list"], "notified_price": notified}
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    print("Kontrol tamam. Fiyat:", fmt(p), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("Hata:", e, file=sys.stderr)
        sys.exit(1)

