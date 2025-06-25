# main.py - Kalahii Promotion System (Final Version)
# This version only handles Roblox group promotion. Discord webhooks are handled by Roblox script.

from flask import Flask, request, jsonify
import os
import requests
import time

app = Flask(__name__)

# --- CONFIGURATION ---
ROBLOX_COOKIE = os.environ.get('ROBLOX_COOKIE')
# Removed: WEBHOOK_URL (since Discord webhooks are handled by Roblox script)
GROUP_ID = 35942189

# --- WEBHOOK FUNCTIONS (All removed as Roblox handles them) ---
# Removed: send_webhook function
# Removed: send_success_webhook function
# Removed: send_failure_webhook function
# Removed: send_command_failure_webhook function


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
        print(f"Error getting CSRF token: {e}") # Keep this for critical internal errors
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

    # Extract only necessary info for Roblox promotion
    # Removed: username, points, currentRankName, newRankName from extraction as API no longer uses for webhooks
    user_id = data.get('userId'); new_role_id = data.get('newRoleId'); source = data.get('source', 'AUTOMATIC')

    if not all([user_id, new_role_id]): # Only userId and newRoleId are strictly needed now
        return jsonify({"success": False, "error": "Missing required fields (userId, newRoleId)"}), 400

    token = get_csrf_token()
    if not token:
        reason = "Failed to get CSRF token. The ranking bot's cookie is likely invalid or expired."
        # No webhook call from here; Roblox script will handle it
        return jsonify({"success": False, "error": reason}), 500

    url = f"https://groups.roblox.com/v1/groups/{GROUP_ID}/users/{user_id}"
    headers = {"X-CSRF-TOKEN": token}
    payload = {"roleId": new_role_id}

    try:
        response = session.patch(url, headers=headers, json=payload)

        if response.status_code == 200:
            # Removed: send_success_webhook call
            return jsonify({"success": True, "message": "Promotion successful"}), 200
        else:
            reason = parse_roblox_error(response)
            # Removed: send_failure_webhook / send_command_failure_webhook calls
            return jsonify({"success": False, "error": reason}), response.status_code

    except requests.exceptions.RequestException as e:
        reason = f"Network Error trying to reach Roblox API: {str(e)}"
        # Removed: send_failure_webhook / send_command_failure_webhook calls
        return jsonify({"success": False, "error": reason}), 500

@app.route('/')
def home():
    return "Kalahii Promotion API is running."

if __name__ == '__main__':
    # IMPORTANT: Do not run app.run() in production on Render.
    # Gunicorn handles the serving. This is only for local testing.
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 8080)) # Use PORT env var for local dev, if set