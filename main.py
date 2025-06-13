from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.models import TextSendMessage, MessageEvent, TextMessage
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date

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
        # 取得今天日期，轉為純數字字串格式如 20250613
        today = date.today()
        records = sheet.get_all_records()

        # 比對時也轉換資料表中的日期格式（去除斜線與補零）
        matched = next((
            row for row in records
            if isinstance(row.get("日期")], date) and row["日期"] == today), None)

        if matched:
            sell_price = matched.get("飾金賣出")
            buy_price = matched.get("飾金買入")
            bar_price = matched.get("條金")
            msg = (
                f"📅 今日金價報價：\n"
                f"🔸 飾金賣出：{sell_price} 元/錢\n"
                f"🔹 飾金買入：{buy_price} 元/錢\n"
                f"🪙 條金參考：{bar_price} 元/錢"
            )
        else:
            msg = f"❗ 未找到今天的金價資料，請稍後再試或聯繫店家。"

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))


