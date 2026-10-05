import os
import requests
from datetime import datetime, timezone, timedelta

GRAPHQL_URL = "https://www.joyalukkas.in/graphql?query=query+getgoldrates%7Bgetgoldrates%7BId+Message+Status+metal_rate_time+Data%7BId+BRANCH_CODE+BRANCH_NAME+GOLD_14KT_RATE+GOLD_18KT_RATE+GOLD_22KT_RATE+GOLD_24KT_RATE+SILVER_RATE+SILVER_RATE100+SILVER_RATE999+PLATINUM_RATE+__typename%7D__typename%7D%7D&operationName=getgoldrates&variables=%7B%7D"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "*/*",
    "Referer": "https://www.joyalukkas.in/",
    "content-type": "application/json"
}

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
EVENT_NAME = os.environ.get("GITHUB_EVENT_NAME", "")
STATE_FILE = "last_rate.txt"

def fetch_gold_rate():
    r = requests.get(GRAPHQL_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    payload = r.json()

    block = payload["data"]["getgoldrates"]
    rows = block.get("Data", [])
    if not rows:
        raise ValueError("No gold rate rows returned")

    row = rows[0]
    return {
        "rate": str(row["GOLD_22KT_RATE"]),
        "branch": row.get("BRANCH_NAME", "Unknown"),
        "rate_time": block.get("metal_rate_time", ""),
    }

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()

def main():
    result = fetch_gold_rate()
    current_rate = result['rate']
    
    last_rate = None
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            last_rate = f.read().strip()
            
    # If triggered via Telegram or manual run, always send.
    # If scheduled (cron), only send if the rate changed.
    is_on_demand = EVENT_NAME in ["repository_dispatch", "workflow_dispatch"]

    if not is_on_demand and current_rate == last_rate:
        print(f"Scheduled check: rate unchanged (₹{current_rate}). No message sent.")
        return

    ist_offset = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(ist_offset).strftime("%Y-%m-%d %H:%M:%S IST")
    
    trend = ""
    if last_rate and current_rate != last_rate:
        try:
            diff = float(current_rate) - float(last_rate)
            trend = f" (🔺 Up ₹{abs(diff):.2f})" if diff > 0 else f" (🔻 Down ₹{abs(diff):.2f})"
        except ValueError:
            pass

    msg = (
        f"Joyalukkas India 22K gold rate: <b>₹{current_rate}</b>{trend}\n"
        f"Branch: {result['branch']}\n"
        f"Rate time: {result['rate_time']}\n"
        f"Checked at: {now}"
    )
    
    send_telegram_message(msg)
    print("Message sent successfully:\n", msg)
    
    with open(STATE_FILE, "w") as f:
        f.write(current_rate)

if __name__ == "__main__":
    main()
