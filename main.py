from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.models import TextSendMessage, MessageEvent, TextMessage, PostbackEvent
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

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"
    
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    if text in ["金價", "查詢黃金報價", "黃金報價"]:
        reply_gold_price(event.reply_token)

@handler.add(PostbackEvent)
def handle_postback(event):
    data = event.postback.data
    if data == "action=gold":
        reply_gold_price(event.reply_token)

def reply_gold_price(reply_token):
        today = datetime.now().strftime("%Y/%-m/%-d")  # mac/linux
        alt_today = datetime.now().strftime("%Y/%#m/%#d")  # Windows
        records = sheet.get_all_records()

        matched = next(
            (row for row in records if str(row.get("日期")).strip() in [today, alt_today]),
            None
        )

        if matched:
            sell_price = matched.get("飾金賣出", "N/A")
            buy_price = matched.get("飾金買入", "N/A")
            bar_price = matched.get("條金", "N/A")
            data_str = str(matched.get("日期", ""))
            time_str = str(matched.get("時間", ""))
            msg = (
                f"報價時間：{date_str} {time_str}"
                f"今日黃金報價：\n"
                f"飾金賣出：{sell_price} 元/錢\n"
                f"飾金買入：{buy_price} 元/錢\n"
                f"條金參考：{bar_price} 元/錢"
            )
        else:
            msg = "系統出了一點問題，請聯繫店家。"

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))


