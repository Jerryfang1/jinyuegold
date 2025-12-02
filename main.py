from flask import Flask, request, abort
from datetime import datetime, timedelta
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# LINE SDK v3
from linebot.v3.webhook import WebhookHandler
from linebot.v3.messaging.models import FlexContainer
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    FlexMessage,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent as V3TextMessageContent,
    PostbackEvent
)

app = Flask(__name__)


print("Token is:", os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
if os.getenv("LINE_CHANNEL_ACCESS_TOKEN") is None:
    raise Exception("❌ 沒有設定 LINE_CHANNEL_ACCESS_TOKEN！請回 Railway 補上環境變數")

configuration = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
api_client = ApiClient(configuration)
line_bot_api = MessagingApi(api_client)
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
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    
    print("=== LINE Webhook Debug ===")
    print("X-Line-Signature:", signature)
    print("Request Body:", body)
    try:
        handler.handle(body, signature)
    except Exception as e:
        print(f"Webhook Error: {e}")
        abort(400)
    return "OK"

@handler.add(PostbackEvent)
def handle_postback(event):
    data = event.postback.data

    if data == "action=gold":
        reply_gold_price(event.reply_token)

    elif data == "action=recycle":
        reply_recycle_info(event.reply_token)


def reply_gold_price(reply_token):
    today = datetime.now()
    today_str = today.strftime("%Y/%m/%d")
    print(f"[DEBUG] 查詢今日金價，今日日期：{today_str}")

    try:
        records = sheet.get_all_records()
    except Exception as e:
        error_msg = f"無法讀取報價資料：{str(e)}"
        print("[ERROR] Google Sheet 讀取錯誤：", error_msg)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=error_msg)]
            )
        )
        return
    matched = None
    used_date_str = None

    for i in range(0, 60):
        check_date = (today - timedelta(days=i)).strftime("%Y/%m/%d")
        print(f"[DEBUG] 嘗試日期：{check_date}")

        matched = next(
            (row for row in records
             if str(row.get("日期", "")).strip() == check_date),
            None
        )
        
        if matched:
            used_date_str = check_date
            break

    print("[DEBUG] matched 資料：", matched)

    if not matched:
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=f"⚠️ 找不到最近 60 天內報價資料（從 {today_str} 往前算），請聯繫店家。")]
            )
        )
        return

    print(f"[DEBUG] 最終使用日期：{used_date_str}")

    # 取值
    gold_sell = int(matched.get("黃金賣出", "N/A")) - 300
    gold_buy = int(matched.get("黃金買入", "N/A")) + 100
    pt_sell = int(matched.get("鉑金賣出", "N/A")) - 100
    pt_buy = int(matched.get("鉑金買入", "N/A")) + 100
    date_str = matched.get("日期", "")
    week_str = matched.get("星期", "")
    time_str = matched.get("時間", "")

    # 建立 Flex Message 卡片
    with open("gold_flex.json", "r", encoding="utf-8") as f:
        template_str = f.read()
    # 替換內容（記得 JSON 內使用的 placeholder 必須是獨特的字，例如 {GOLD_SELL}）
    template_str = (
        template_str
        .replace("{DATE}", date_str)
        .replace("{TIME}", time_str)
        .replace("{WEEKDAY}", week_str)
        .replace("{GOLD_SELL}", str(gold_sell))
        .replace("{GOLD_BUY}", str(gold_buy))
        .replace("{PT_SELL}", str(pt_sell))
        .replace("{PT_BUY}", str(pt_buy))
    )
    
    # 轉回 dict 格式
    flex_dict = json.loads(template_str)

    line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[
                FlexMessage(
                    alt_text="今日金價",
                    contents=FlexContainer.from_dict(flex_dict)
                )
            ]
        )
    )

def reply_recycle_info(reply_token):
    with open("recycle_flex.json", "r", encoding="utf-8") as f:
        recycle_json = json.load(f)
    
    line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[
                FlexMessage(
                    alt_text="黃金回收流程介紹",
                    contents=FlexContainer.from_dict(recycle_json)
                )
            ]
        )
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))


