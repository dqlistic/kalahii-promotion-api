# main.py - Kalahii Promotion System (Final Version)
# Uses cookie-based authentication and handles all webhook logic.

from flask import Flask, request, jsonify
import os
import requests
import time

app = Flask(__name__)

# --- CONFIGURATION ---
ROBLOX_COOKIE = os.environ.get('ROBLOX_COOKIE')
WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
GROUP_ID = 35942189

# --- WEBHOOK FUNCTIONS ---

def send_webhook(data, webhook_type="general"):
    """Centralized function to send webhooks and log responses/errors."""
    if not WEBHOOK_URL:
        print(f"[{webhook_type}] ERROR: DISCORD_WEBHOOK_URL is not set.")
        return

    try:
        response = requests.post(WEBHOOK_URL, json=data)
        response.raise_for_status() # Raises an HTTPError for bad responses (4xx or 5xx)
        print(f"[{webhook_type}] Webhook sent successfully. Status: {response.status_code}")
        # Optionally, print response content if you want to debug further
        # print(f"[{webhook_type}] Webhook response: {response.text}")
    except requests.exceptions.HTTPError as e:
        print(f"[{webhook_type}] HTTP Error sending webhook: {e.response.status_code} - {e.response.text}")
    except requests.exceptions.RequestException as e:
        print(f"[{webhook_type}] Network Error sending webhook: {e}")
    except Exception as e:
        print(f"[{webhook_type}] Unexpected Error sending webhook: {e}")


def send_success_webhook(username, user_id, old_rank_name, new_rank_name, points):
    """Sends a green-tagged embed for a successful promotion."""
    data = {
        "embeds": [{
            "title": "Promotion Successful",
            "color": 3066993,  # Green
            "fields": [
                {"name": "Username", "value": str(username), "inline": True},
                {"name": "User ID", "value": str(user_id), "inline": True},
                {"name": "Points", "value": str(points), "inline": False},
                {"name": "Previous Rank", "value": str(old_rank_name), "inline": True},
                {"name": "New Rank", "value": str(new_rank_name), "inline": True}
            ]
        }]
    }
    send_webhook(data, "success") # Call the new centralized function

def send_failure_webhook(username, user_id, current_rank_name, supposed_rank_name, points, reason):
    """Sends a red-tagged embed for a system failure during an automatic promotion."""
    data = {
        "embeds": [{
            "title": "Promotion System Failure",
            "color": 15158332,  # Red
            "description": "The system failed to promote a user who met the requirements.",
            "fields": [
                {"name": "Username", "value": str(username), "inline": True},
                {"name": "User ID", "value": str(user_id), "inline": True},
                {"name": "Points", "value": str(points), "inline": False},
                {"name": "Current Rank", "value": str(current_rank_name), "inline": True},
                {"name": "Supposed Rank", "value": str(supposed_rank_name), "inline": True},
                {"name": "Reason for Failure", "value": f"```{reason}```", "inline": False}
            ]
        }]
    }
    send_webhook(data, "failure") # Call the new centralized function

def send_command_failure_webhook(username, user_id, current_rank_name, points, reason):
    """Sends a yellow-tagged embed for a command-triggered failure where the user was eligible."""
    data = {
        "embeds": [{
            "title": "Command Promotion Failure",
            "color": 16705372,  # Yellow
            "description": "A promotion initiated by the `!rank` command failed.",
            "fields": [
                {"name": "Username", "value": str(username), "inline": True},
                {"name": "User ID", "value": str(user_id), "inline": True},
                {"name": "Points", "value": str(points), "inline": False},
                {"name": "Current Rank", "value": str(current_rank_name), "inline": True},
                {"name": "Reason", "value": f"```{reason}```", "inline": False}
            ]
        }]
    }
    send_webhook(data, "command_failure") # Call the new centralized function


# --- CORE LOGIC ---
session = requests.Session()
session.cookies['.ROBLOSECURITY'] = ROBLOX_COOKIE
csrf_token = None
csrf_last_fetched = 0

def get_csrf_token():
    global csrf_token, csrf_last_fetched
    if time.time() - csrf_last_fetched < 300 and csrf_token:
        return csrf_token
    try:
        response = session.post("https://auth.roblox.com/v2/logout")
        if response.status_code == 403 and 'x-csrf-token' in response.headers:
            csrf_token = response.headers['x-csrf-token']
            csrf_last_fetched = time.time()
            return csrf_token
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error getting CSRF token: {e}")
        return None

def parse_roblox_error(response):
    """Attempts to parse a clean, user-facing error message from Roblox's API response."""
    try:
        error_data = response.json()
        if "errors" in error_data and isinstance(error_data["errors"], list) and len(error_data["errors"]) > 0:
            error_info = error_data["errors"][0]
            if "userFacingMessage" in error_info and error_info["userFacingMessage"]:
                return error_info["userFacingMessage"]
            elif "message" in error_info and error_info["message"]:
                return error_info["message"]
    except (ValueError, KeyError):
        pass
    return f"Roblox API Error {response.status_code}: {response.text}"


@app.route('/promote', methods=['POST'])
def promote_user():
    data = request.json
    if not data: return jsonify({"success": False, "error": "No data provided"}), 400

    # Extract all necessary info
    user_id = data.get('userId'); new_role_id = data.get('newRoleId'); source = data.get('source', 'AUTOMATIC')
    username = data.get('username'); points = data.get('points'); current_rank_name = data.get('currentRankName'); new_rank_name = data.get('newRankName')

    if not all([user_id, new_role_id, username, points, current_rank_name, new_rank_name]):
        return jsonify({"success": False, "error": "Missing required fields"}), 400

    token = get_csrf_token()
    if not token:
        reason = "Failed to get CSRF token. The ranking bot's cookie is likely invalid or expired."
        # This is a critical system error, so we log it for both sources
        if source == 'COMMAND':
            send_command_failure_webhook(username, user_id, current_rank_name, points, reason)
        else:
            send_failure_webhook(username, user_id, current_rank_name, new_rank_name, points, reason)
        return jsonify({"success": False, "error": reason}), 500

    url = f"https://groups.roblox.com/v1/groups/{GROUP_ID}/users/{user_id}"
    headers = {"X-CSRF-TOKEN": token}
    payload = {"roleId": new_role_id}

    try:
        response = session.patch(url, headers=headers, json=payload)

        if response.status_code == 200:
            send_success_webhook(username, user_id, current_rank_name, new_rank_name, points)
            return jsonify({"success": True, "message": "Promotion successful"}), 200
        else:
            reason = parse_roblox_error(response)
            if source == 'COMMAND':
                send_command_failure_webhook(username, user_id, current_rank_name, points, reason)
            else:
                send_failure_webhook(username, user_id, current_rank_name, new_rank_name, points, reason)
            return jsonify({"success": False, "error": reason}), response.status_code

    except requests.exceptions.RequestException as e:
        reason = f"Network Error trying to reach Roblox API: {str(e)}"
        if source == 'COMMAND':
            send_command_failure_webhook(username, user_id, current_rank_name, points, reason)
        else:
            send_failure_webhook(username, user_id, current_rank_name, new_rank_name, points, reason)
        return jsonify({"success": False, "error": reason}), 500

@app.route('/')
def home():
    return "Kalahii Promotion API is running."

if __name__ == '__main__':
    # IMPORTANT: Do not run app.run() in production on Render.
    # Gunicorn handles the serving. This is only for local testing.
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 8080)) # Use PORT env var for local dev, if set