import os
import re
import json
import time
import uuid
import threading
from urllib.parse import quote

import requests as std_requests
from curl_cffi import requests as cffi_requests
from flask import Flask, request, jsonify, Response
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

app = Flask(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "")
SECRET_PROMO_ID = os.environ.get("PROMO_CODE", "")
BASE_URL = os.environ.get("WEB_APP_URL") or os.environ.get("RENDER_EXTERNAL_URL", "")
PROXY_URL = os.environ.get("PROXY_URL", "")

API = "https://chatgpt.com"

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
    #msg { margin-top: 14px; font-size: 13.5px; font-weight: 500; display: none; padding: 10px; border-radius: 8px; line-height: 1.55; }
    .ok { background: #dcfce7; color: #166534; }
    .err { background: #fee2e2; color: #991b1b; }
    .warn { background: #fef9c3; color: #854d0e; }
    #info { display: none; text-align: left; font-size: 12.5px; background: #f3f4f6; border-radius: 10px; padding: 10px 12px; margin-top: 12px; line-height: 1.7; }
    #note { display: none; text-align: left; font-size: 12px; background: #eff6ff; color: #1e3a8a; border-radius: 10px; padding: 10px 12px; margin-top: 10px; line-height: 1.6; }
  </style>
</head>
<body>
  <div class="card">
    <h2>🎁 Ưu Đãi Độc Quyền</h2>
    <p class="sub">Nhận <b>1 tháng ChatGPT Plus (0đ)</b>.<br/>Thực hiện 2 bước để lấy trang kích hoạt cá nhân.</p>

    <div class="step">
      <b>Bước 1:</b> Đăng nhập sẵn <b>chatgpt.com</b> trên trình duyệt, sau đó bấm nút dưới và <b>Sao chép toàn bộ</b> đoạn mã hiện ra.
      <br/><i style="color:#6b7280">Dán thiếu cũng được, miễn trong đó có chữ <b>accessToken</b>.</i>
    </div>
    <button class="btn-session" onclick="openSession()">🔑 Mở lấy Mã Phiên (Session)</button>

    <div class="step">
      <b>Bước 2:</b> Dán mã vừa sao chép vào ô dưới để Bot kiểm tra điều kiện <b>0đ/tháng</b>.
    </div>
    <textarea id="sessionBox" placeholder='Dán nội dung {"user":...,"accessToken":"..."} vào đây'></textarea>

    <button id="submitBtn" class="btn-main" onclick="claimPromo()">Nhận Ưu Đãi Ngay</button>
    <div id="msg"></div>
    <div id="info"></div>
    <div id="note">
      <b>Nếu trang thanh toán báo lỗi tải biểu mẫu:</b> bấm <b>Thử lại</b> 1–2 lần rồi đóng tab, mở lại <b>chatgpt.com</b> → <b>Cài đặt → Gói đăng ký</b>. Gói 0đ vẫn được ghi nhận, không cần nhập thẻ.
    </div>
  </div>

  <script>
    const tg = window.Telegram.WebApp;
    tg.ready();
    tg.expand();

    function openSession() {
      tg.openLink("https://chatgpt.com/api/auth/session");
    }

    function showMsg(text, kind) {
      const el = document.getElementById("msg");
      el.className = kind;
      el.innerText = text;
      el.style.display = "block";
    }

    async function claimPromo() {
      const raw = document.getElementById("sessionBox").value.trim();
      const btn = document.getElementById("submitBtn");
      const info = document.getElementById("info");
      const note = document.getElementById("note");
      info.style.display = "none";
      note.style.display = "none";

      if (!raw) {
        showMsg("Vui lòng dán mã phiên ở Bước 1 vào ô trống!", "err");
        return;
      }

      btn.disabled = true;
      btn.innerText = "⏳ Đang kiểm tra tài khoản...";
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
          showMsg("❌ " + (data.error || "Không kiểm tra được ưu đãi, thử lại sau."), "err");
          return;
        }

        const lines = [];
        if (data.email) lines.push("<b>Tài khoản:</b> " + data.email);
        if (data.plan) lines.push("<b>Gói hiện tại:</b> " + data.plan);
        if (data.price) lines.push("<b>Giá sau ưu đãi:</b> " + data.price);
        if (data.status) lines.push("<b>Kết quả kiểm tra:</b> " + data.status);
        info.innerHTML = lines.join("<br/>");
        info.style.display = "block";

        if (data.promo_applied && data.is_free) {
          showMsg("✅ Đã xác nhận ưu đãi 0đ trên phiên thanh toán. Đang mở trang kích hoạt...", "ok");
        } else if (data.promo_applied) {
          showMsg("⚠️ Đã áp ưu đãi nhưng giá chưa hiển thị 0đ, kiểm tra lại ở trang thanh toán.", "warn");
        } else {
          showMsg("⚠️ " + (data.message || "Tài khoản đủ điều kiện. Đang mở trang kích hoạt, làm theo hướng dẫn bên dưới."), "warn");
          note.style.display = "block";
        }

        if (data.checkout_url) {
          setTimeout(() => { tg.openLink(data.checkout_url); }, 900);
        }
      } catch (e) {
        showMsg("❌ Lỗi kết nối máy chủ, vui lòng thử lại.", "err");
      } finally {
        btn.disabled = false;
        btn.innerText = "Nhận Ưu Đãi Ngay";
      }
    }
  </script>
</body>
</html>
"""


# ---------------------------------------------------------------- helpers

_TOKEN_JSON_RE = re.compile(r'"accessToken"\s*:\s*"([^"]+)"')
_TOKEN_RAW_RE = re.compile(r'(eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,})')


def extract_token(raw_text: str) -> str:
    raw = (raw_text or "").strip()
    if not raw:
        return ""
    raw = raw.replace("\u200b", "").replace("\xa0", " ").replace("&quot;", '"')

    if raw.startswith("{"):
        try:
            token = json.loads(raw).get("accessToken") or ""
            if token:
                return token.strip()
        except Exception:
            pass

    m = _TOKEN_JSON_RE.search(raw)
    if m:
        return m.group(1).strip()

    m = _TOKEN_RAW_RE.search(raw)
    if m:
        return m.group(1).strip()

    if raw.startswith("eyJ"):
        return raw.split()[0].strip('",\'}')

    return ""


def build_headers(token: str, path: str, device_id: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "*/*",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "oai-language": "vi-VN",
        "oai-device-id": device_id,
        "Origin": API,
        "Referer": f"{API}/",
        "x-openai-target-path": path,
        "x-openai-target-route": path,
        "sec-fetch-site": "same-origin",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
    }


def new_client():
    proxies = {"https": PROXY_URL, "http": PROXY_URL} if PROXY_URL else None
    return cffi_requests.Session(impersonate="chrome", proxies=proxies)


def promo_link() -> str:
    """Link ưu đãi trực tiếp - vẫn kích hoạt free dù server bị chặn tạo checkout."""
    return f"{API}/?source=chatgpt_web_merged&promo_campaign={quote(SECRET_PROMO_ID)}"


def is_blocked(resp) -> bool:
    if resp.status_code in (429, 500, 502, 503):
        return True
    try:
        body = resp.text.lower()
    except Exception:
        return False
    return "unusual activity" in body or "try again later" in body


def check_coupon_state(data: dict) -> tuple:
    state = str(data.get("state") or "").lower()
    redemption = data.get("redemption") if isinstance(data.get("redemption"), dict) else {}
    redeemed = bool(redemption.get("redeemed"))
    expires_at = redemption.get("expires_at")

    if state == "eligible" and not redeemed:
        return True, "ELIGIBLE", "Đủ điều kiện nhận ưu đãi."

    if redeemed or state in ("redeemed", "already_redeemed", "used"):
        return False, "REDEEMED", "Tài khoản này đã dùng ưu đãi này rồi (mỗi tài khoản chỉ nhận 1 lần)."

    if state in ("expired", "coupon_expired"):
        return False, "EXPIRED", "Ưu đãi đã hết hạn hoặc hết lượt phát hành."

    if state in ("not_eligible", "ineligible", "not_found", "invalid", "invalid_coupon"):
        return False, "NOT_ELIGIBLE", (
            "Tài khoản không đủ điều kiện: ưu đãi chỉ áp cho tài khoản ChatGPT Free "
            "chưa từng dùng gói trả phí."
        )

    if not state:
        if data.get("is_eligible") is True or data.get("valid") is True:
            return True, "ELIGIBLE", "Đủ điều kiện nhận ưu đãi."
        return False, "NOT_ELIGIBLE", "Tài khoản không đủ điều kiện nhận ưu đãi."

    extra = f" (trạng thái: {state}"
    if expires_at:
        extra += f", hết hạn: {expires_at}"
    extra += ")"
    return False, "UNKNOWN", f"Ưu đãi không dùng được cho tài khoản này{extra}."


def verify_checkout(client, token: str, device_id: str, session_id: str):
    path = f"/backend-api/payments/checkout/openai_llc/{session_id}"
    try:
        r = client.get(API + path, headers=build_headers(token, path, device_id), timeout=15)
        if r.status_code != 200:
            return None, None, f"HTTP {r.status_code}"
        data = r.json()
    except Exception as e:
        return None, None, str(e)

    blob = json.dumps(data, ensure_ascii=False).lower()
    applied = any(k in blob for k in (
        "promo_campaign", "promo_code", "immediate_discount_settings", "scheduled_discount_preview"
    ))

    amount = None
    for key in ("amount_due", "amount_total", "total", "amount"):
        val = data.get(key)
        if isinstance(val, (int, float)):
            amount = val
            break
    currency = (data.get("currency") or "").upper() or None

    price = f"{(amount / 100):,.2f} {currency or ''}".strip() if amount is not None else None
    return applied, price, "ok"


def is_zero(price) -> bool:
    if not price:
        return False
    try:
        return float(price.replace(",", "").split()[0]) == 0.0
    except Exception:
        return False


def notify_telegram_success(chat_id, url: str, email: str = "", price: str = "", fallback: bool = False):
    if not chat_id or not TOKEN:
        return
    try:
        head = "⚠️ *Đủ điều kiện — mở link để kích hoạt ưu đãi*" if fallback else "🎉 *Đã tạo phiên kích hoạt ưu đãi 0đ/tháng!*"
        lines = [head, ""]
        if email:
            lines.append(f"👤 Tài khoản: `{email}`")
        if price:
            lines.append(f"💵 Giá sau ưu đãi: *{price}*")
        if fallback:
            lines.append("Nếu trang báo lỗi tải biểu mẫu: bấm Thử lại rồi đóng tab, gói vẫn được ghi nhận.")
        lines.append("Bấm nút bên dưới:")
        payload = {
            "chat_id": chat_id,
            "text": "\n".join(lines),
            "parse_mode": "Markdown",
            "reply_markup": {"inline_keyboard": [[{"text": "💳 Mở trang kích hoạt", "url": url}]]},
        }
        std_requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json=payload, timeout=10)
    except Exception:
        pass


def with_promo(url: str) -> str:
    if "promo_campaign=" in url or "promoCode=" in url or "promo_code=" in url:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}promo_campaign={quote(SECRET_PROMO_ID)}"


# ---------------------------------------------------------------- routes

@app.route("/")
def home():
    return "Bot is running!"


@app.route("/health")
def health():
    return jsonify({"ok": True})


@app.route("/miniapp")
def serve_miniapp():
    return Response(MINIAPP_HTML, mimetype="text/html")


@app.route("/api/claim", methods=["POST"])
def api_claim():
    if not SECRET_PROMO_ID:
        return jsonify({"success": False, "error": "Chưa cấu hình PROMO_CODE trên Render."}), 500

    body = request.get_json(silent=True) or {}
    token = extract_token(body.get("session_raw", ""))
    chat_id = body.get("chat_id")

    if not token:
        return jsonify({
            "success": False,
            "code": "TOKEN_INVALID",
            "error": "Không tìm thấy mã phiên. Bấm nút Bước 1, đăng nhập chatgpt.com rồi copy lại đoạn có chữ accessToken.",
        }), 400

    device_id = str(uuid.uuid4())

    try:
        with new_client() as client:
            # 1. Xác thực phiên
            me_path = "/backend-api/me"
            me = client.get(API + me_path, headers=build_headers(token, me_path, device_id), timeout=15)

            if me.status_code == 401:
                return jsonify({
                    "success": False,
                    "code": "TOKEN_INVALID",
                    "error": "Phiên đăng nhập đã hết hạn hoặc mã bị cắt. Đăng nhập lại chatgpt.com rồi copy lại đầy đủ.",
                }), 401
            if me.status_code == 403:
                return jsonify({
                    "success": False,
                    "error": "IP server đang bị Cloudflare chặn (403). Gắn biến PROXY_URL trên Render.",
                }), 502

            me_data = me.json() if me.status_code == 200 else {}
            email = me_data.get("email") or ""
            plan = me_data.get("plan_type") or me_data.get("account_plan") or "free"
            country = (me_data.get("country") or "VN").upper()
            plan_display = plan
            if str(plan).lower() in ("plus", "pro", "team", "business"):
                plan_display = f"{plan} (ưu đãi chỉ áp cho tài khoản Free)"

            # 2. Kiểm tra điều kiện bằng field `state`
            chk_path = "/backend-api/promo_campaign/check_coupon"
            chk_url = f"{API}{chk_path}?coupon={quote(SECRET_PROMO_ID)}&is_coupon_from_query_param=true"
            chk = client.get(chk_url, headers=build_headers(token, chk_path, device_id), timeout=15)

            if chk.status_code == 401:
                return jsonify({
                    "success": False,
                    "code": "TOKEN_INVALID",
                    "error": "Phiên đăng nhập hết hạn, lấy lại mã phiên mới.",
                }), 401
            if chk.status_code == 403:
                return jsonify({
                    "success": False,
                    "error": "Bị Cloudflare chặn (403) ở bước kiểm tra ưu đãi. Gắn PROXY_URL trên Render.",
                }), 502

            if chk.status_code == 200:
                ok, code, message = check_coupon_state(chk.json())
                if not ok:
                    return jsonify({
                        "success": False,
                        "code": code,
                        "email": email,
                        "plan": plan_display,
                        "error": message,
                    }), 400

            # 3. Tạo phiên checkout — retry 3 lần, đổi device id mỗi lần
            co_path = "/backend-api/payments/checkout"
            co_data = None
            co_device = None
            last_error = ""
            blocked = False
            currencies = ["USD"] if country in ("VN", "US") else ["USD", "EUR"]

            for attempt in range(3):
                co_device = str(uuid.uuid4())
                for currency in currencies:
                    co_payload = {
                        "entry_point": "all_plans_pricing_modal",
                        "plan_name": "chatgptplusplan",
                        "billing_details": {"country": country, "currency": currency},
                        "promo_campaign": {
                            "promo_campaign_id": SECRET_PROMO_ID,
                            "is_coupon_from_query_param": True,
                        },
                        "checkout_ui_mode": "redirect",
                        "checkout_source": "chatgpt_web_merged",
                        "supports_saved_payment_link": True,
                        "purchase_attempt_id": str(uuid.uuid4()),
                        "cancel_url": promo_link(),
                    }
                    co = client.post(
                        API + co_path,
                        headers=build_headers(token, co_path, co_device),
                        json=co_payload,
                        timeout=25,
                    )
                    if co.status_code == 200:
                        co_data = co.json()
                        break
                    if co.status_code == 401:
                        return jsonify({
                            "success": False,
                            "code": "TOKEN_INVALID",
                            "error": "Phiên đăng nhập hết hạn, lấy lại mã phiên mới.",
                        }), 401
                    blocked = is_blocked(co)
                    try:
                        last_error = json.dumps(co.json(), ensure_ascii=False)[:200]
                    except Exception:
                        last_error = f"HTTP {co.status_code}"
                if co_data:
                    break
                if not blocked:
                    break
                time.sleep(1.5)

            # 4a. Server bị chặn / không tạo được phiên -> trả link ưu đãi trực tiếp
            if not co_data:
                if blocked:
                    notify_telegram_success(chat_id, promo_link(), email, "", fallback=True)
                    return jsonify({
                        "success": True,
                        "email": email,
                        "plan": plan_display,
                        "status": "Tài khoản đủ điều kiện (OpenAI chặn tạo phiên tự động)",
                        "promo_applied": False,
                        "is_free": False,
                        "fallback": True,
                        "message": (
                            "Tài khoản của bạn đủ điều kiện. Hệ thống vừa bị OpenAI chặn tạm thời nên "
                            "chuyển sang link ưu đãi trực tiếp — vẫn nhận được 1 tháng 0đ."
                        ),
                        "checkout_url": promo_link(),
                    })

                return jsonify({
                    "success": False,
                    "email": email,
                    "plan": plan_display,
                    "error": f"OpenAI từ chối tạo phiên thanh toán: {last_error}",
                }), 400

            # 4b. Có phiên -> verify giá thật
            raw_url = co_data.get("url") or ""
            session_id = co_data.get("checkout_session_id") or ""
            if not raw_url:
                notify_telegram_success(chat_id, promo_link(), email, "", fallback=True)
                return jsonify({
                    "success": True,
                    "email": email,
                    "plan": plan_display,
                    "status": "Đủ điều kiện, dùng link ưu đãi trực tiếp",
                    "promo_applied": False,
                    "is_free": False,
                    "fallback": True,
                    "message": "Đã dùng link ưu đãi trực tiếp thay cho phiên thanh toán.",
                    "checkout_url": promo_link(),
                })

            checkout_url = with_promo(raw_url)
            applied, price, detail = (None, None, "")
            if session_id:
                applied, price, detail = verify_checkout(client, token, co_device, session_id)

            if applied is False and not price:
                # phiên không xác nhận được -> link trực tiếp an toàn hơn
                notify_telegram_success(chat_id, promo_link(), email, "", fallback=True)
                return jsonify({
                    "success": True,
                    "email": email,
                    "plan": plan_display,
                    "status": "Không xác nhận được ưu đãi trên phiên, đã chuyển link trực tiếp",
                    "promo_applied": False,
                    "is_free": False,
                    "fallback": True,
                    "verify": detail,
                    "message": "Tài khoản đủ điều kiện. Mở link và hoàn tất, gói 0đ vẫn được ghi nhận.",
                    "checkout_url": promo_link(),
                })

            notify_telegram_success(chat_id, checkout_url, email, price or "")

            return jsonify({
                "success": True,
                "email": email,
                "plan": plan_display,
                "price": price,
                "promo_applied": bool(applied),
                "is_free": is_zero(price),
                "status": "Đã áp ưu đãi" if applied else "Chưa xác nhận ưu đãi trên phiên",
                "verify": detail,
                "checkout_url": checkout_url,
            })

    except Exception as e:
        return jsonify({"success": False, "error": f"Lỗi kết nối máy chủ: {e}"}), 500


def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = f"{BASE_URL.rstrip('/')}/miniapp"
    keyboard = [[InlineKeyboardButton("🎁 Nhận ưu đãi ChatGPT", web_app=WebAppInfo(url=url))]]
    await update.message.reply_text(
        "Chào bạn! Bấm nút bên dưới để kiểm tra và mở khóa ưu đãi 1 tháng ChatGPT Plus (0đ):",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.run_polling()
