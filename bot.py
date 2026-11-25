import os
import json
import threading
import requests as std_requests
from curl_cffi import requests as cffi_requests
from flask import Flask, request, jsonify, Response
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

app = Flask(__name__)

# LẤY BIẾN MÔI TRƯỜNG TỪ RENDER (KHÔNG LỘ TRONG CODE GITHUB)
TOKEN = os.environ.get("BOT_TOKEN", "")
SECRET_PROMO_ID = os.environ.get("PROMO_CODE", "")
# Render tự động có sẵn biến RENDER_EXTERNAL_URL (VD: https://ten-app.onrender.com)
BASE_URL = os.environ.get("WEB_APP_URL") or os.environ.get("RENDER_EXTERNAL_URL", "")
# Tùy chọn: Điền Proxy dân cư nếu IP của Render bị Cloudflare chặn (403)
PROXY_URL = os.environ.get("PROXY_URL", "")

MINIAPP_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
  <title>ChatGPT Free</title>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <style>
    * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    body { margin: 0; padding: 20px 16px; background: #f8faf9; color: #1f2937; text-align: center; }
    .card { background: #fff; border-radius: 18px; padding: 22px 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.06); }
    h2 { margin: 0 0 8px; font-size: 20px; color: #111827; }
    p.sub { margin: 0 0 16px; font-size: 14px; color: #4b5563; line-height: 1.45; }
    .step { text-align: left; background: #f3f4f6; padding: 11px 13px; border-radius: 10px; margin-bottom: 12px; font-size: 13px; line-height: 1.45; }
    .btn-session { width: 100%; padding: 12px; border-radius: 10px; border: 1.5px solid #199473; background: #ecfdf5; color: #0d8a6a; font-weight: 600; font-size: 14px; margin-bottom: 14px; cursor: pointer; }
    textarea { width: 100%; height: 90px; padding: 10px; border-radius: 10px; border: 1px solid #d1d5db; font-size: 12.5px; resize: none; margin-bottom: 14px; outline: none; }
    textarea:focus { border-color: #199473; }
    .btn-main { width: 100%; padding: 15px; border-radius: 12px; border: none; background: #199473; color: #fff; font-weight: 600; font-size: 16px; cursor: pointer; }
    .btn-main:disabled { opacity: 0.6; }
    #msg { margin-top: 14px; font-size: 13.5px; font-weight: 500; display: none; padding: 10px; border-radius: 8px; }
    .ok { background: #dcfce7; color: #166534; }
    .err { background: #fee2e2; color: #991b1b; }
  </style>
</head>
<body>
  <div class="card">
    <h2>🎁 Ưu Đãi Độc Quyền</h2>
    <p class="sub">Nhận <b>1 tháng ChatGPT Plus (0đ)</b>.<br/>Thực hiện 2 bước để lấy trang kích hoạt cá nhân.</p>

    <div class="step">
      <b>Bước 1:</b> Đăng nhập sẵn <b>chatgpt.com</b> trên trình duyệt, sau đó bấm nút dưới và <b>Sao chép toàn bộ</b> đoạn mã hiện ra.
    </div>
    <button class="btn-session" onclick="openSession()">🔑 Mở lấy Mã Phiên (Session)</button>

    <div class="step">
      <b>Bước 2:</b> Dán mã vừa sao chép vào ô dưới để Bot kiểm tra điều kiện <b>0đ/tháng</b>.
    </div>
    <textarea id="sessionBox" placeholder='Dán nội dung {"user":...,"accessToken":"..."} vào đây'></textarea>

    <button id="submitBtn" class="btn-main" onclick="claimPromo()">Nhận Ưu Đãi Ngay</button>
    <div id="msg"></div>
  </div>

  <script>
    const tg = window.Telegram.WebApp;
    tg.ready();
    tg.expand();

    function openSession() {
      tg.openLink("https://chatgpt.com/api/auth/session");
    }

    async function claimPromo() {
      const raw = document.getElementById("sessionBox").value.trim();
      const btn = document.getElementById("submitBtn");
      if (!raw) {
        showMsg("Vui lòng dán mã phiên ở Bước 1 vào ô trống!", false);
        return;
      }

      btn.disabled = true;
      btn.innerText = "⏳ Đang kiểm tra gói 0đ...";
      document.getElementById("msg").style.display = "none";

      const userId = tg.initDataUnsafe && tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : null;

      try {
        const res = await fetch("/api/claim", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_raw: raw, chat_id: userId })
        });
        const data = await res.json();

        if (!res.ok || !data.success) {
          showMsg("❌ " + (data.error || "Tài khoản không đủ điều kiện nhận 0đ."), false);
        } else {
          showMsg("✅ Đủ điều kiện 0đ/tháng! Bot đã gửi thông báo & đang mở trang kích hoạt...", true);
          setTimeout(() => {
            tg.openLink(data.checkout_url);
          }, 800);
        }
      } catch (e) {
        showMsg("❌ Lỗi kết nối máy chủ, vui lòng thử lại.", false);
      } finally {
        btn.disabled = false;
        btn.innerText = "Nhận Ưu Đãi Ngay";
      }
    }

    function showMsg(text, ok) {
      const el = document.getElementById("msg");
      el.className = ok ? "ok" : "err";
      el.innerText = text;
      el.style.display = "block";
    }
  </script>
</body>
</html>
"""


def extract_token(raw_text: str) -> str:
    raw_text = raw_text.strip()
    if raw_text.startswith("{"):
        try:
            return json.loads(raw_text).get("accessToken", "")
        except Exception:
            return ""
    if raw_text.startswith("eyJ") and len(raw_text) > 50:
        return raw_text
    return ""


def notify_telegram_success(chat_id, clean_url: str):
    if not chat_id or not TOKEN:
        return
    try:
        api_url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": (
                "🎉 *Xác nhận ưu đãi 0đ/tháng thành công!*\n\n"
                "Tài khoản ChatGPT của bạn đã được kích hoạt phiên thanh toán *₫0 / tháng*.\n"
                "Bấm nút bên dưới để hoàn tất nhận gói Plus:"
            ),
            "parse_mode": "Markdown",
            "reply_markup": {
                "inline_keyboard": [[
                    {"text": "💳 Mở trang thanh toán 0đ", "url": clean_url}
                ]]
            }
        }
        std_requests.post(api_url, json=payload, timeout=10)
    except Exception:
        pass


@app.route("/")
def home():
    return "Bot is running!"


@app.route("/miniapp")
def serve_miniapp():
    return Response(MINIAPP_HTML, mimetype="text/html")


@app.route("/api/claim", methods=["POST"])
def api_claim():
    if not SECRET_PROMO_ID:
        return jsonify({"success": False, "error": "Chưa cấu hình PROMO_CODE trên Render."}), 500

    body = request.get_json(silent=True) or {}
    access_token = extract_token(body.get("session_raw", ""))
    chat_id = body.get("chat_id")

    if not access_token:
        return jsonify({"success": False, "error": "Mã phiên không hợp lệ hoặc bạn chưa đăng nhập ChatGPT!"}), 400

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": "https://chatgpt.com",
        "Referer": "https://chatgpt.com/",
    }
    proxies = {"https": PROXY_URL, "http": PROXY_URL} if PROXY_URL else None

    try:
        with cffi_requests.Session(impersonate="chrome", proxies=proxies) as client:
            # 1. Kiểm tra điều kiện nhận mã 0đ
            check_url = (
                f"https://chatgpt.com/backend-api/promo_campaign/check_coupon"
                f"?coupon={SECRET_PROMO_ID}&is_coupon_from_query_param=true"
            )
            chk = client.get(check_url, headers=headers, timeout=15)

            if chk.status_code == 401:
                return jsonify({"success": False, "error": "Phiên đăng nhập đã hết hạn, hãy lấy lại mã mới."}), 401
            if chk.status_code == 403:
                return jsonify({"success": False, "error": "IP Render đang bị Cloudflare chặn (403). Hãy gắn thêm biến PROXY_URL trên Render."}), 502

            if chk.status_code == 200:
                chk_data = chk.json()
                if chk_data.get("is_eligible") is False or chk_data.get("valid") is False:
                    return jsonify({"success": False, "error": "Tài khoản này không đủ điều kiện nhận gói 0đ/tháng."}), 400

            # 2. Tạo phiên Checkout 0đ ẩn mã từ phía Server Render
            co_payload = {
                "plan_name": "chatgptplusplan",
                "billing_details": {"country": "VN", "currency": "USD"},
                "promo_campaign": {
                    "promo_campaign_id": SECRET_PROMO_ID,
                    "is_coupon_from_query_param": True
                },
                "checkout_ui_mode": "redirect"
            }
            co_resp = client.post(
                "https://chatgpt.com/backend-api/payments/checkout",
                headers=headers,
                json=co_payload,
                timeout=20
            )

            if co_resp.status_code != 200:
                return jsonify({
                    "success": False,
                    "error": "Tài khoản không áp được ưu đãi 0đ (đã từng dùng Plus hoặc hết lượt ưu đãi)."
                }), 400

            raw_url = co_resp.json().get("url", "")
            if not raw_url:
                return jsonify({"success": False, "error": "Không tạo được phiên thanh toán từ OpenAI."}), 500

            # 3. Cắt bỏ hoàn toàn đuôi ?source=...&promo_campaign=...
            clean_url = raw_url.split("?")[0]

            # 4. Tự động nhắn tin báo thành công vào Telegram của khách
            notify_telegram_success(chat_id, clean_url)

            return jsonify({"success": True, "checkout_url": clean_url})

    except Exception as e:
        return jsonify({"success": False, "error": f"Lỗi kết nối: {str(e)}"}), 500


def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    miniapp_url = f"{BASE_URL.rstrip('/')}/miniapp"
    keyboard = [
        [InlineKeyboardButton("🎁 Nhận ưu đãi ChatGPT", web_app=WebAppInfo(url=miniapp_url))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Chào bạn! Bấm nút bên dưới để kiểm tra và mở khóa ưu đãi 1 tháng ChatGPT Plus (0đ):",
        reply_markup=reply_markup
    )


if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.run_polling()
