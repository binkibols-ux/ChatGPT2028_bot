import os
import json
import threading
from flask import Flask
from curl_cffi import requests as cffi_requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# LINK MINI APP NETLIFY CŨ CỦA BÁC
WEB_APP_URL = "https://gentle-crepe-382315.netlify.app"
PROMO_CODE = os.environ.get("PROMO_CODE", "plus-1-month-free")
ADMIN_ID = os.environ.get("ADMIN_ID")  # Điền ID Telegram của bác trên Render nếu muốn nhận thông báo
PROXY_URL = os.environ.get("PROXY_URL", "")


def check_promo_eligibility(raw_text: str) -> dict:
    raw_text = raw_text.strip()
    if not raw_text.startswith("{"):
        return {"status": "invalid", "msg": "⚠️ Dữ liệu không đúng định dạng! Hãy sao chép toàn bộ nội dung từ trang lấy mã phiên (bắt đầu bằng dấu `{`)."}

    try:
        session_data = json.loads(raw_text)
    except Exception:
        return {"status": "invalid", "msg": "⚠️ Mã phiên bị cắt thiếu chữ! Vui lòng Chọn tất cả (Select All) và sao chép lại."}

    token = session_data.get("accessToken")
    email = session_data.get("user", {}).get("email", "Không rõ email")
    plan_in_session = session_data.get("account", {}).get("planType", "free")

    if not token:
        return {"status": "invalid", "msg": "❌ Bạn chưa đăng nhập ChatGPT trên trình duyệt này (mã rỗng `{}`). Hãy đăng nhập trước rồi lấy lại mã!"}

    # Trường hợp 1: Ngay trong mã phiên đã ghi nhận tài khoản đang có gói Plus (vừa kích hoạt 0đ xong)
    if plan_in_session == "plus":
        return {
            "status": "activated",
            "email": email,
            "msg": f"🎉 **Xác nhận thành công!**\nTài khoản `{email}` đã kích hoạt gói **ChatGPT Plus**!"
        }

    # Trường hợp 2: Tài khoản đang là Free -> Hỏi trực tiếp API OpenAI xem có được nhận gói 0đ không
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Origin": "https://chatgpt.com",
        "Referer": "https://chatgpt.com/",
    }
    proxies = {"https": PROXY_URL, "http": PROXY_URL} if PROXY_URL else None

    try:
        with cffi_requests.Session(impersonate="chrome", proxies=proxies) as client:
            # Kiểm tra trạng thái tài khoản mới nhất trên máy chủ OpenAI
            acc_resp = client.get(
                "https://chatgpt.com/backend-api/accounts/check/v4-2023-04-27",
                headers=headers,
                timeout=15
            )
            if acc_resp.status_code == 401:
                return {"status": "invalid", "msg": "❌ Phiên đăng nhập đã hết hạn, vui lòng mở lấy mã mới."}
            if acc_resp.status_code == 403:
                return {"status": "error", "msg": "⚠️ Máy chủ kiểm tra đang bận (Cloudflare 403). Cần gắn thêm PROXY_URL trên Render."}

            if acc_resp.status_code == 200:
                acc_json = acc_resp.json()
                accounts = acc_json.get("accounts", {})
                default_acc = accounts.get("default", {})
                entitlement = default_acc.get("entitlement", {})

                # Nếu vừa thanh toán 0đ xong nhưng session cũ chưa kịp cập nhật
                if entitlement.get("has_active_subscription") is True:
                    return {
                        "status": "activated",
                        "email": email,
                        "msg": f"🎉 **Xác nhận thành công!**\nTài khoản `{email}` đã nhận gói **ChatGPT Plus** thành công!"
                    }

                # Kiểm tra nếu tài khoản từng đăng ký gói trả phí trước đây (thường sẽ mất quyền 0đ)
                was_paid = default_acc.get("account", {}).get("was_paid_customer", False)

            # Gọi API kiểm tra trực tiếp mã khuyến mãi 0đ (chỉ GET nhẹ, không POST tạo đơn nên không lỗi tiền tệ)
            promo_url = (
                f"https://chatgpt.com/backend-api/promo_campaign/check_coupon"
                f"?coupon={PROMO_CODE}&is_coupon_from_query_param=true"
            )
            chk_resp = client.get(promo_url, headers=headers, timeout=15)

            if chk_resp.status_code == 200:
                chk_data = chk_resp.json()
                # Xét các cờ trả về của OpenAI
                if chk_data.get("is_eligible") is False or chk_data.get("valid") is False:
                    return {
                        "status": "ineligible",
                        "email": email,
                        "msg": f"❌ **Không đủ điều kiện!**\nTài khoản `{email}` không áp dụng được ưu đãi 0đ/tháng. Vui lòng thử bằng tài khoản khác!"
                    }
                return {
                    "status": "eligible",
                    "email": email,
                    "msg": f"✅ **Tài khoản hợp lệ nhận ưu đãi 0đ/tháng!**\nEmail: `{email}`\n*(Hiện chưa thêm thẻ thanh toán — bạn hãy bấm Nhận ưu đãi miễn phí trên web để kích hoạt lên Plus nhé)*."
                }
            else:
                # Nếu API check_coupon trả mã lỗi 400/404 -> Tài khoản không được hưởng hoặc từng mua Plus
                if was_paid:
                    return {
                        "status": "ineligible",
                        "email": email,
                        "msg": f"❌ **Không đủ điều kiện!**\nTài khoản `{email}` đã từng sử dụng gói trả phí trước đây nên không được nhận 0đ."
                    }
                return {
                    "status": "ineligible",
                    "email": email,
                    "msg": f"❌ Tài khoản `{email}` không nhận được ưu đãi 0đ (Mã phản hồi: {chk_resp.status_code})."
                }

    except Exception as e:
        return {"status": "error", "msg": f"⚠️ Lỗi kết nối khi kiểm tra: {str(e)}"}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎁 Nhận ưu đãi ChatGPT", web_app=WebAppInfo(url=WEB_APP_URL))],
        [InlineKeyboardButton("✅ Kiểm tra đã nhận được ưu đãi chưa", callback_data="verify")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Chào bạn! Bấm nút bên dưới để mở khóa ưu đãi 1 tháng ChatGPT Plus miễn phí:",
        reply_markup=reply_markup
    )


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "verify":
        kb = [[InlineKeyboardButton("🔑 Mở trang lấy mã kiểm tra", url="https://chatgpt.com/api/auth/session")]]
        await query.message.reply_text(
            "🔍 **Cách kiểm tra tự động (không cần gửi ảnh):**\n\n"
            "1️⃣ Bấm nút bên dưới để mở trang mã phiên trên trình duyệt bạn vừa đăng nhập ChatGPT.\n"
            "2️⃣ **Chọn tất cả (Select All)** $\\rightarrow$ **Sao chép (Copy)** toàn bộ chữ trên màn hình.\n"
            "3️⃣ Dán trực tiếp vào khung chat này và gửi cho Bot!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb)
        )


async def handle_session_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    # Tự động xóa ngay tin nhắn chứa token của khách để bảo mật cho khách
    if text.strip().startswith("{") and "accessToken" in text:
        try:
            await update.message.delete()
        except Exception:
            pass

    wait_msg = await update.message.reply_text("⏳ Đang kiểm tra trạng thái ưu đãi trên hệ thống...")
    result = check_promo_eligibility(text)
    await wait_msg.edit_text(result["msg"], parse_mode="Markdown")

    # Báo tự động về Telegram của bác (nếu bác có cài ADMIN_ID trên Render)
    if ADMIN_ID and result["status"] in ("activated", "eligible", "ineligible"):
        user = update.effective_user
        admin_text = (
            f"🔔 **Báo cáo kiểm tra ưu đãi**\n"
            f"👤 Khách: {user.full_name} (@{user.username or 'không có'})\n"
            f"📧 Email ChatGPT: `{result.get('email')}`\n"
            f"📊 Kết quả: **{result['status'].upper()}**"
        )
        try:
            await context.bot.send_message(chat_id=int(ADMIN_ID), text=admin_text, parse_mode="Markdown")
        except Exception:
            pass


if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    TOKEN = os.environ.get("BOT_TOKEN")
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_session_text))
    application.run_polling()
