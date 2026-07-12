import os
import traceback
from flask import Flask, request, jsonify, redirect
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")


@app.before_request
def log_all_requests():
    print(f">>> INCOMING: {request.method} {request.path} from {request.remote_addr}")


def _process(phone_number, text):
    from src.brain.decision_layer import process_message
    return process_message(phone_number, text)


def _send(phone_number, reply):
    from src.whatsapp.client import send_message
    send_message(phone_number, reply)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200

    return jsonify({"error": "forbidden"}), 403


@app.route("/webhook", methods=["POST"])
def receive_webhook():
    print("CHECKPOINT 1: webhook POST received")
    print("Content-Type:", request.content_type)

    data = request.get_json(force=True, silent=True)
    if data is None:
        print("CHECKPOINT 2 FAILED: could not parse JSON body")
        print("Raw body:", request.get_data(as_text=True)[:500])
        return jsonify({"status": "received"}), 200

    print("CHECKPOINT 2: JSON parsed OK")

    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]
        messages = value.get("messages")
        print("CHECKPOINT 3: payload parsed, messages:", bool(messages))
    except Exception as e:
        print("CHECKPOINT 3 FAILED: payload parse error:", repr(e))
        return jsonify({"status": "received"}), 200

    if not messages:
        print("CHECKPOINT 4: no messages in payload (status update or other event)")
        return jsonify({"status": "received"}), 200

    print("CHECKPOINT 4: message found")

    phone_number = messages[0]["from"]
    message_type = messages[0].get("type")
    print("CHECKPOINT 5: from:", phone_number, "type:", message_type)

    if message_type == "text":
        text = messages[0]["text"]["body"]
    elif message_type == "image":
        image_id = messages[0].get("image", {}).get("id", "")
        text = f"__image__:{image_id}"
    elif message_type == "audio":
        text = "__audio__"
    else:
        print("CHECKPOINT 6 SKIP: unsupported message type:", message_type)
        return jsonify({"status": "received"}), 200

    print("CHECKPOINT 6: type:", message_type, "text:", text[:80])

    try:
        reply = _process(phone_number, text)
        print("CHECKPOINT 7: process OK, reply length:", len(reply))
    except Exception as e:
        print("CHECKPOINT 7 FAILED: _process error:", repr(e))
        return jsonify({"status": "received"}), 200

    try:
        parts = reply.split("\n||||\n")
        for part in parts:
            if part.strip():
                _send(phone_number, part.strip())
        print("CHECKPOINT 8: send_message called, parts:", len(parts))
    except Exception as e:
        print("CHECKPOINT 8 FAILED: _send error:", repr(e))

    return jsonify({"status": "received"}), 200


@app.route("/auth/meta")
def auth_meta():
    from src.services.identity import IdentityService
    from src.db.repositories.auth_session import AuthSessionRepository
    from src.specialists.auth.oauth import generate_oauth_url

    phone = request.args.get("phone")
    if not phone:
        return "<h2>Missing ?phone= parameter</h2>", 400

    try:
        identity = IdentityService()
        user, business = identity.resolve("whatsapp", phone)
    except ValueError as e:
        print("IDENTITY ERROR:", repr(e))
        return f"<h2>Identity error</h2><p>{e}</p>", 400

    session_repo = AuthSessionRepository()
    state = session_repo.create(
        business_id=business.id,
        channel="whatsapp",
        channel_user_id=phone,
        initiated_by=user.id,
    )

    url = generate_oauth_url(state)
    print("OAUTH URL:", url)
    return redirect(url)


@app.route("/connect/<state>")
def connect_redirect(state):
    from src.db.repositories.auth_session import AuthSessionRepository
    from src.specialists.auth.oauth import generate_oauth_url

    try:
        AuthSessionRepository().validate_exists(state)
    except ValueError as e:
        return (
            "<h2>הקישור פג תוקף</h2>"
            "<p>קישורי חיבור תקפים ל-60 דקות.</p>"
            "<p>חזרי לוואטסאפ ושלחי כל הודעה — מיה תשלח לך קישור חדש.</p>"
        ), 400

    url = generate_oauth_url(state)
    return redirect(url)


@app.route("/auth/meta/callback")
def auth_meta_callback():
    from src.db.repositories.auth_session import AuthSessionRepository
    from src.db.repositories.social_account import SocialAccountRepository
    from src.specialists.auth.oauth import exchange_code_for_token, get_long_lived_token, get_connected_assets
    from datetime import datetime, timedelta, timezone

    error = request.args.get("error")
    if error:
        print("OAUTH ERROR:", error, request.args.get("error_description"))
        return f"<h2>Authentication failed</h2><p>{error}</p>", 400

    code = request.args.get("code")
    state = request.args.get("state")

    if not state or not code:
        return "<h2>Missing parameters</h2>", 400

    try:
        session = AuthSessionRepository().consume(state)
    except ValueError as e:
        print("SESSION ERROR:", repr(e))
        return f"<h2>Invalid or expired session</h2><p>{e}</p>", 400

    business_id = session["business_id"]

    try:
        short_token = exchange_code_for_token(code)
        long_lived = get_long_lived_token(short_token)
        access_token = long_lived["access_token"]
        expires_in = long_lived.get("expires_in", 0)
        token_expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()

        assets = get_connected_assets(access_token)

        social_repo = SocialAccountRepository()

        for ig in assets["instagram_accounts"]:
            social_repo.upsert(
                business_id=business_id,
                platform="instagram",
                platform_account_id=ig["ig_user_id"],
                record={
                    "account_username": ig.get("username"),
                    "account_display_name": ig.get("name"),
                    "page_id": ig.get("linked_page_id"),
                    "page_name": ig.get("linked_page_name"),
                    "access_token": access_token,
                    "token_expires_at": token_expires_at,
                    "metadata": ig,
                },
            )

        for page in assets["pages"]:
            social_repo.upsert(
                business_id=business_id,
                platform="facebook",
                platform_account_id=page["id"],
                record={
                    "account_display_name": page["name"],
                    "page_id": page["id"],
                    "page_name": page["name"],
                    "access_token": access_token,
                    "token_expires_at": token_expires_at,
                    "metadata": {
                        **page,
                        "page_access_token": page.get("page_access_token"),
                    },
                },
            )

        print("=== CONNECTED ASSETS ===")
        print("Pages:", assets["pages"])
        print("Instagram accounts:", assets["instagram_accounts"])
        print("========================")

        # Verify permissions and send WhatsApp feedback
        phone = session.get("channel_user_id")
        whatsapp_msg = _build_connection_feedback(access_token, assets)
        if phone:
            try:
                from src.whatsapp.client import send_message
                send_message(phone, whatsapp_msg)
            except Exception as we:
                print("WHATSAPP FEEDBACK ERROR:", repr(we))

        return "<h2>✅ Connected!</h2><p>חזרי לוואטסאפ — מיה שלחה לך אישור.</p>", 200

    except Exception as e:
        print("OAUTH CALLBACK ERROR:", repr(e))
        return f"<h2>Error</h2><pre>{repr(e)}</pre>", 500


def _build_connection_feedback(user_token: str, assets: dict) -> str:
    import requests as req
    app_token = f"{os.getenv('META_APP_ID')}|{os.getenv('META_APP_SECRET')}"

    try:
        debug = req.get(
            "https://graph.facebook.com/debug_token",
            params={"input_token": user_token, "access_token": app_token},
            timeout=10,
        ).json()
        granted = set(debug.get("data", {}).get("scopes", []))
    except Exception:
        granted = set()

    required_for_facebook = {"pages_manage_posts", "pages_read_engagement"}
    missing_facebook = required_for_facebook - granted

    has_instagram = bool(assets.get("instagram_accounts"))
    has_ig_publish = "instagram_content_publish" in granted

    pages = assets.get("pages", [])
    ig_accounts = assets.get("instagram_accounts", [])

    lines = ["✅ התחברת בהצלחה!\n"]

    if pages:
        lines.append(f"📘 פייסבוק: {', '.join(p['name'] for p in pages)}")
        if missing_facebook:
            lines.append(f"   ⚠️ חסרה הרשאה לפרסום: {', '.join(missing_facebook)}")
        else:
            lines.append("   ✅ הרשאות פרסום תקינות")

    if ig_accounts:
        ig_names = [ig.get("username") or ig.get("name", "") for ig in ig_accounts]
        lines.append(f"📸 אינסטגרם: {', '.join(ig_names)}")
        if has_ig_publish:
            lines.append("   ✅ הרשאת פרסום תקינה")
        else:
            lines.append("   ⚠️ חסרה הרשאת instagram_content_publish")

    if not pages and not ig_accounts:
        lines.append("⚠️ לא נמצאו דפים או חשבונות אינסטגרם מחוברים.")

    return "\n".join(lines)


@app.route("/debug/token-permissions")
def debug_token_permissions():
    import requests as req
    phone = request.args.get("phone")
    if not phone:
        return "<pre>Missing ?phone= param</pre>", 400

    from src.specialists.memory.engine import get_user, get_business
    from src.db.repositories.social_account import SocialAccountRepository

    user = get_user(phone)
    if not user:
        return f"<pre>User not found: {phone}</pre>", 404
    business = get_business(user.id)
    if not business:
        return "<pre>No business found</pre>", 404

    accounts = SocialAccountRepository().get_by_business(business.id, platform="facebook")
    if not accounts:
        return "<pre>No Facebook accounts stored</pre>", 404

    account = accounts[0]
    user_token = account.get("access_token")
    page_token = (account.get("metadata") or {}).get("page_access_token")
    page_id = account.get("page_id")

    app_token = f"{os.getenv('META_APP_ID')}|{os.getenv('META_APP_SECRET')}"

    r1 = req.get("https://graph.facebook.com/debug_token",
                 params={"input_token": user_token, "access_token": app_token})
    r2 = req.get("https://graph.facebook.com/debug_token",
                 params={"input_token": page_token, "access_token": app_token}) if page_token else None

    import json
    result = {
        "page_id": page_id,
        "has_page_token": bool(page_token),
        "user_token_info": r1.json(),
        "page_token_info": r2.json() if r2 else "no page token stored",
    }
    return f"<pre>{json.dumps(result, indent=2, ensure_ascii=False)}</pre>", 200


@app.route("/debug/subscribe-waba", methods=["POST"])
def subscribe_waba():
    import requests as req
    app_id = os.getenv("META_APP_ID")
    app_secret = os.getenv("META_APP_SECRET")
    waba_id = "1382473903744883"
    app_token = f"{app_id}|{app_secret}"
    res = req.post(
        f"https://graph.facebook.com/v21.0/{waba_id}/subscribed_apps",
        headers={"Authorization": f"Bearer {app_token}"},
    )
    print("SUBSCRIBE WABA status:", res.status_code)
    print("SUBSCRIBE WABA body:", res.text)
    return jsonify({"status": res.status_code, "body": res.json()}), 200


@app.route("/debug/test", methods=["GET"])
def debug_test():
    try:
        reply = _process("972525383871", "היי")
        return reply, 200, {"Content-Type": "text/plain; charset=utf-8"}
    except Exception:
        return traceback.format_exc(), 500, {"Content-Type": "text/plain; charset=utf-8"}


@app.route("/debug/simulate-message", methods=["POST"])
def simulate_message():
    try:
        data = request.get_json()
        phone_number = data.get("phone_number")
        text = data.get("text")
        reply = _process(phone_number, text)
        return jsonify({"reply": reply, "status": "ok"}), 200
    except Exception:
        return jsonify({"error": traceback.format_exc()}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
