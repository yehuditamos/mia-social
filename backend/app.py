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
    from src.specialists.auth.oauth import generate_oauth_url
    url = generate_oauth_url()
    print("OAUTH URL GENERATED:", url)
    return redirect(url)


@app.route("/auth/meta/callback")
def auth_meta_callback():
    from src.specialists.auth.oauth import validate_state, exchange_code_for_token, get_long_lived_token, get_connected_assets

    error = request.args.get("error")
    if error:
        print("OAUTH ERROR:", error, request.args.get("error_description"))
        return f"<h2>Authentication failed</h2><p>{error}</p>", 400

    code = request.args.get("code")
    state = request.args.get("state")

    if not state or not validate_state(state):
        print("INVALID OR EXPIRED STATE:", state)
        return "<h2>Invalid or expired session</h2><p>Please try again.</p>", 400

    if not code:
        return "<h2>Missing authorization code</h2>", 400

    try:
        short_token = exchange_code_for_token(code)
        long_lived = get_long_lived_token(short_token)
        assets = get_connected_assets(long_lived["access_token"])

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
