import os
import threading
from flask import Flask, Response
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

app = Flask(__name__)

# Tự động lấy tên miền Render của bạn để chạy Mini App (không dùng Netlify nữa)
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
PROMO_LINK = os.environ.get(
    "PROMO_LINK",
    "https://chatgpt.com/?source=chatgpt_web_merged&promo_campaign=plus-1-month-free",
)
ADMIN_ID = os.environ.get("ADMIN_ID", "").strip()


@app.route("/")
def home():
    return "Bot is running!"


@app.route("/miniapp")
def miniapp_page():
    html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
  <title>ChatGPT Free</title>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <style>
    * {{ box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
    body {{ margin: 0; padding: 48px 20px; background: #f8faf9; color: #111827; text-align: center; }}
    h2 {{ margin: 0 0 14px; font-size: 22px; font-weight: 700; }}
    p {{ margin: 0 0 24px; font-size: 15px; color: #4b5563; line-height: 1.5; }}
    .btn {{ width: 100%; max-width: 360px; padding: 16px; border: none; border-radius: 12px; background: #199473; color: #ffffff; font-size: 16px; font-weight: 600; cursor: pointer; }}
  </style>
</head>
<body>
  <h2>🎁 Ưu Đãi Độc Quyền</h2>
  <p>Bạn đã đủ điều kiện nhận <b>1 tháng ChatGPT Plus miễn phí</b>.<br><br>Vui lòng bấm nút bên dưới để tiếp tục.</p>
  <button class="btn" onclick="openPromo()">Nhận Ưu Đãi Ngay</button>

  <script>
    const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
    if (tg) {{
      tg.ready();
      tg.expand();
    }}
    function openPromo() {{
      const url = "{PROMO_LINK}";
      if (tg && tg.openLink) {{
        tg.openLink(url);
      }} else {{
        window.open(url, "_blank");
      }}
    }}
  </script>
</body>
</html>"""
    return Response(html, mimetype="text/html")


def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    miniapp_url = f"{RENDER_URL}/miniapp" if RENDER_URL else PROMO_LINK
    keyboard = [
        [InlineKeyboardButton("🎁 Nhận ưu đãi ChatGPT", web_app=WebAppInfo(url=miniapp_url))],
        [InlineKeyboardButton("✅ Tôi đã nhận thành công", callback_data="verify")],
    ]
    await update.message.reply_text(
        "Chào bạn! Bấm nút bên dưới để mở khóa ưu đãi 1 tháng ChatGPT Plus miễn phí:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "verify":
        user = query.from_user
        await query.edit_message_text(
            "🎉 Chúc mừng! Hệ thống đã ghi nhận bạn kích hoạt ưu đãi 1 tháng ChatGPT Plus miễn phí thành công."
        )
        if ADMIN_ID.isdigit():
            try:
                await context.bot.send_message(
                    chat_id=int(ADMIN_ID),
                    text=f"✅ Khách {user.full_name} (@{user.username or 'không có'} - ID: {user.id}) vừa xác nhận đã nhận ưu đãi.",
                )
            except Exception:
                pass


if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    token = os.environ.get("BOT_TOKEN", "")
    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))
    application.run_polling()
