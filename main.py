from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.models import TextSendMessage, MessageEvent, TextMessage, PostbackEvent, FlexSendMessage
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
        error_msg = f"無法讀取報價資料：{str(e)}"
        line_bot_api.reply_message(reply_token, TextSendMessage(text=error_msg))
        return

    matched = next(
        (row for row in records if str(row.get("日期", "")).strip() in [today, alt_today]),
        None
    )
    
    if not matched:
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text=f"⚠️ 找不到今日（{today}）報價資料，請聯繫店家。")
        )
        return

    # 取值
    gold_sell = matched.get("黃金賣出", "N/A")
    gold_buy = matched.get("黃金買入", "N/A")
    pt_sell = matched.get("鉑金賣出", "N/A")
    pt_buy = matched.get("鉑金買入", "N/A")
    date_str = matched.get("日期", "")
    time_str = matched.get("時間", "")

    # 建立 Flex Message 卡片
    msg = FlexSendMessage(
        alt_text="今日金屬報價",
        contents={
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "報價時間",
                        "weight": "bold",
                        "color": "#1C1C1C",
                        "size": "lg"
                    },
                    {
                        "type": "text",
                        "text": f"🗓️ {date_str} {time_str}",
                        "weight": "bold",
                        "color": "#B08B4F",
                        "size": "lg"
                    }
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {
                        "type": "box",
                        "layout": "baseline",
                        "contents": [
                            {"type": "text", "text": "👑 黃金", "weight": "bold", "flex": 1}
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {"type": "text", "text": "🟡 賣出", "flex": 2},
                            {"type": "text", "text": f"{gold_sell} 元／錢", "flex": 3, "align": "end"}
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {"type": "text", "text": "⚪ 買入", "flex": 2},
                            {"type": "text", "text": f"{gold_buy} 元／錢", "flex": 3, "align": "end"}
                        ]
                    },
                    {
                        "type": "separator",
                        "margin": "lg"
                        "color": "#9E8254FF"
                    },
                    {
                        "type": "box",
                        "layout": "baseline",
                        "contents": [
                            {"type": "text", "text": "💎 鉑金", "weight": "bold", "flex": 1}
                        ],
                        "margin": "md"
                    },
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {"type": "text", "text": "🟣 賣出", "flex": 2},
                            {"type": "text", "text": f"{pt_sell} 元／錢", "flex": 3, "align": "end"}
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {"type": "text", "text": "⚪ 買入", "flex": 2},
                            {"type": "text", "text": f"{pt_buy} 元／錢", "flex": 3, "align": "end"}
                        ]
                    }
                ]
            }
        }
    )

    line_bot_api.reply_message(reply_token, msg)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))


