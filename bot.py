import os
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

app = Flask(__name__)
@app.route('/')
def home(): return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# LINK NETLIFY CỦA BÁC
WEB_APP_URL = "https://gentle-crepe-302315.netlify.app" 

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎁 Nhận ưu đãi ChatGPT", web_app=WebAppInfo(url=WEB_APP_URL))],
        [InlineKeyboardButton("✅ Tôi đã nhận thành công", callback_data="verify")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Chào bạn! Bấm nút bên dưới để mở khóa ưu đãi 1 tháng ChatGPT Plus.", reply_markup=reply_markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "verify":
        await query.edit_message_text(text="Vui lòng gửi ảnh chụp màn hình gói 0đ của bạn vào đây để Admin kiểm duyệt.")

if __name__ == '__main__':
    threading.Thread(target=run_flask).start()
    TOKEN = os.environ.get('BOT_TOKEN')
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))
    application.run_polling()
