from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.models import TextSendMessage, MessageEvent, TextMessage
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date

app = Flask(__name__)

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# Google Sheets 授權設定
credentials_json = json.loads(os.environ["GOOGLE_APPLICATION_CREDENTIALS_JSON"])
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_json, scope)
client = gspread.authorize(creds)

# 打開 Sheet
sheet = client.open("金玥報價").worksheet("金價")

@app.route("/webhook", methods=['POST'])
def webhook():
    body = request.get_data(as_text=True)
    signature = request.headers['X-Line-Signature']
    handler.handle(body, signature)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()

    if text in ["查詢金價", "查詢黃金報價", "黃金報價"]:
        today = date.today()

        # 產生幾種可接受的日期格式（可能出現在 Google Sheet 中）
        possible_dates = [
            today.strftime("%Y/%#m/%#d"),  # e.g. 2025/6/13 (windows)
            today.strftime("%Y/%m/%d"),    # e.g. 2025/06/13
            today.strftime("%Y-%m-%d"),    # e.g. 2025-06-13
        ]

        records = sheet.get_all_records()

        matched = next(
            (row for row in records
             if str(row.get("日期")) in possible_dates),
            None
        )

        if matched:
            sell_price = matched.get("飾金賣出", "N/A")
            buy_price = matched.get("飾金買入", "N/A")
            bar_price = matched.get("條金", "N/A")
            msg = (
                f"📅 今日金價報價：\\n"
                f"🔸 飾金賣出：{sell_price} 元/錢\\n"
                f"🔹 飾金買入：{buy_price} 元/錢\\n"
                f"🪙 條金參考：{bar_price} 元/錢"
            )
        else:
            msg = "❗ 未找到今天的金價資料，請稍後再試或聯繫店家。"

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))


