from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.models import TextSendMessage, MessageEvent, TextMessage, PostbackEvent
from linebot.exceptions import InvalidSignatureError
from datetime import datetime
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials


app = Flask(__name__)

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# Google Sheets 授權設定
credentials_json = json.loads(os.environ["GOOGLE_APPLICATION_CREDENTIALS_JSON"])
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_json, scope)
client = gspread.authorize(creds)

# 打開 Sheet
sheet = client.open("金玥報價").worksheet("報價")

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
    if text == "查詢今日金價":
        reply_gold_price(event.reply_token)

@handler.add(PostbackEvent)
def handle_postback(event):
    data = event.postback.data
    if data == "action=gold":
        reply_gold_price(event.reply_token)

def reply_gold_price(reply_token):
    today = datetime.now().strftime("%Y/%m/%d")
    alt_today = datetime.now().strftime("%Y-%m-%d")  # 因應不同日期格式

    try:
        records = sheet.get_all_records()
    except Exception as e:
        error_msg = f"無法讀取報價表：{str(e)}"
        line_bot_api.reply_message(reply_token, TextSendMessage(text=error_msg))
        return

    matched = next(
        (row for row in records if str(row.get("日期", "")).strip() in [today, alt_today]),
        None
    )
    if matched:
            gold_sell = matched.get("黃金賣出", "N/A")
            gold_buy = matched.get("黃金買入", "N/A")
            pt_sell = matched.get("鉑金賣出", "N/A")
            pt_buy = matched.get("鉑金買入", "N/A")
            date_str = str(matched.get("日期", ""))
            time_str = str(matched.get("時間", ""))
            msg = (
                f"報價時間：{date_str} {time_str}"
                f"今日黃金報價：\n"
                f"黃金賣出：{gold_sell} 元/錢\n"
                f"黃金買入：{gold_buy} 元/錢\n"
                f"鉑金賣出：{pt_sell} 元/錢\n"
                f"鉑金買入：{pt_buy} 元/錢\n"
            )
    else:
        all_dates = [str(row.get("日期", "")).strip() for row in records]
        msg = "⚠️ 找不到今日報價資料。\n目前日期清單：\n" + "\n".join(all_dates)
    line_bot_api.reply_message(reply_token, TextSendMessage(text=msg))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))


