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
    data = request.get_json()
    print("WEBHOOK POST RECEIVED")
    print(data)
    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]
        messages = value.get("messages")

        if messages:
            phone_number = messages[0]["from"]
            message_type = messages[0].get("type")

            if message_type == "text":
                text = messages[0]["text"]["body"]
                print("MESSAGE RECEIVED FROM:", phone_number)
                print("MESSAGE TEXT:", text)
                print("PROCESS START")
                reply = _process(phone_number, text)
                print("PROCESS FINISHED — reply:", reply)
                _send(phone_number, reply)

    except Exception as e:
        print("WEBHOOK ERROR:", repr(e))

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
                    "metadata": page,
                },
            )

        print("=== CONNECTED ASSETS ===")
        print("Pages:", assets["pages"])
        print("Instagram accounts:", assets["instagram_accounts"])
        print("========================")

        return "<h2>Connected successfully!</h2><p>Check Render logs for the connected assets.</p>", 200

    except Exception as e:
        print("OAUTH CALLBACK ERROR:", repr(e))
        return f"<h2>Error</h2><pre>{repr(e)}</pre>", 500


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
