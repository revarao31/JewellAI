
import os
import time
import random
import logging
from pathlib import Path
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, request, send_file
from dotenv import load_dotenv

# --------------------------------------------------
# Configuration
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent

load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)
app.json.ensure_ascii = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jewellai")

GEMINI_API_KEY = (
    os.getenv("GEMINI_API_KEY")
    or os.getenv("GOOGLE_API_KEY")
    or ""
).strip()

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL", "gemini-2.5-flash"
).strip()

OROPOCKET_API_KEY = os.getenv("OROPOCKET_API_KEY", "").strip()
OROPOCKET_URL = "https://api.oropocket.com/public/prices"


# --------------------------------------------------
# Frontend
# --------------------------------------------------

@app.route("/")
def home():
    frontend_file = PROJECT_DIR / "frontend" / "index.html"

    if frontend_file.exists():
        return send_file(frontend_file)

    return jsonify({
        "status": "error",
        "message": "frontend/index.html was not found",
        "expected_path": str(frontend_file)
    }), 404


# --------------------------------------------------
# Health check
# --------------------------------------------------

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "JewellAI",
        "gemini_configured": bool(GEMINI_API_KEY),
        "gemini_model": GEMINI_MODEL,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), 200


# --------------------------------------------------
# Gemini API request with retry
# --------------------------------------------------

def generate_gemini_response(url, payload):
    retry_statuses = {429, 500, 502, 503, 504}
    last_response = None

    for attempt in range(3):
        try:
            response = requests.post(
                url,
                params={"key": GEMINI_API_KEY},
                json=payload,
                timeout=45
            )

            last_response = response

            if (
                response.status_code not in retry_statuses
                or attempt == 2
            ):
                return response

            delay = (2 ** attempt) + random.uniform(0.2, 0.8)

            logger.warning(
                "Gemini returned HTTP %s. Attempt %s/3. "
                "Retrying in %.1f seconds.",
                response.status_code,
                attempt + 1,
                delay
            )

            time.sleep(delay)

        except requests.RequestException:
            if attempt == 2:
                raise

            delay = (2 ** attempt) + random.uniform(0.2, 0.8)

            logger.warning(
                "Gemini connection failed. Attempt %s/3. "
                "Retrying in %.1f seconds.",
                attempt + 1,
                delay
            )

            time.sleep(delay)

    return last_response


# --------------------------------------------------
# Gemini chatbot
# --------------------------------------------------

@app.route("/api/chat", methods=["POST"])
def chat():
    if not request.is_json:
        return jsonify({
            "error": "Request must contain JSON."
        }), 400

    body = request.get_json(silent=True) or {}
    message = str(body.get("message", "")).strip()

    if not message:
        return jsonify({
            "error": "Please enter a message."
        }), 400

    if not GEMINI_API_KEY:
        logger.error("Gemini API key is missing.")

        return jsonify({
            "error": (
                "Gemini API key is missing. "
                "Check GEMINI_API_KEY in backend/.env."
            )
        }), 503

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent"
    )

    payload = {
        "system_instruction": {
            "parts": [{
                "text": (
                    "You are JewellAI, a helpful and professional Smart "
                    "Jewellery Assistant. Help users with gold and silver "
                    "jewellery, purity, hallmarking, diamonds, jewellery care, "
                    "buying advice, styling and Indian jewellery traditions. "
                    "Be friendly, clear and informative. Never invent live "
                    "prices. For current rates, explain that prices depend "
                    "on the latest rate feed, location, purity and jeweller."
                )
            }]
        },
        "contents": [{
            "role": "user",
            "parts": [{"text": message}]
        }],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1200
        }
    }

    try:
        response = generate_gemini_response(url, payload)

        if response is None:
            return jsonify({
                "error": "Gemini did not return a response."
            }), 502

        if not response.ok:
            try:
                error_data = response.json()
                detail = error_data.get(
                    "error", {}
                ).get("message", "Gemini request failed.")
            except ValueError:
                detail = "Gemini returned an unexpected response."

            logger.error(
                "Gemini API HTTP %s: %s",
                response.status_code,
                detail
            )

            if response.status_code in (401, 403):
                return jsonify({
                    "error": (
                        "Gemini API key is invalid or lacks permission. "
                        "Check your key and model access."
                    )
                }), 502

            if response.status_code == 429:
                return jsonify({
                    "error": (
                        "Gemini rate limit reached after retries. "
                        "Please wait before trying again."
                    )
                }), 429

            if response.status_code == 503:
                return jsonify({
                    "error": (
                        "Gemini is experiencing high demand, even after "
                        "automatic retries. Please try again shortly. "
                        "If this continues, verify the model in Google AI Studio."
                    )
                }), 503

            if response.status_code == 404:
                return jsonify({
                    "error": (
                        f"Gemini model '{GEMINI_MODEL}' was not found. "
                        "Check the exact model ID in Google AI Studio."
                    )
                }), 502

            return jsonify({
                "error": (
                    f"Gemini API error ({response.status_code}): {detail}"
                )
            }), 502

        result = response.json()
        candidates = result.get("candidates", [])

        if not candidates:
            block_reason = (
                result.get("promptFeedback", {}).get("blockReason")
                or "No response was returned."
            )

            return jsonify({
                "error": f"Gemini could not answer: {block_reason}"
            }), 502

        parts = candidates[0].get(
            "content", {}
        ).get("parts", [])

        reply = "\n".join(
            part["text"]
            for part in parts
            if isinstance(part, dict) and part.get("text")
        ).strip()

        if not reply:
            return jsonify({
                "error": "Gemini returned an empty reply. Please try again."
            }), 502

        return jsonify({
            "status": "success",
            "reply": reply
        }), 200

    except requests.Timeout:
        logger.exception("Gemini request timed out.")

        return jsonify({
            "error": (
                "Gemini took too long to respond after retries. "
                "Please try again."
            )
        }), 504

    except requests.RequestException:
        logger.exception("Unable to reach Gemini.")

        return jsonify({
            "error": (
                "Could not connect to Gemini. Check your internet connection."
            )
        }), 502

    except Exception:
        logger.exception("Unexpected error in /api/chat.")

        return jsonify({
            "error": "Unexpected server error while generating a reply."
        }), 500


# --------------------------------------------------
# OroPocket gold and silver rates
# --------------------------------------------------

def fetch_market_prices():
    headers = {
        "Accept": "application/json",
        "User-Agent": "JewellAI/1.0"
    }

    if OROPOCKET_API_KEY:
        headers["Authorization"] = (
            f"Bearer {OROPOCKET_API_KEY}"
        )

    response = requests.get(
        OROPOCKET_URL,
        headers=headers,
        timeout=15
    )

    response.raise_for_status()
    payload = response.json()

    if not isinstance(payload, dict):
        raise ValueError("Unexpected rate-provider response.")

    data = payload.get("data", payload)

    if not isinstance(data, dict):
        raise ValueError("Rate-provider data is missing.")

    return data, payload


def get_metal_rate(metal):
    try:
        data, original = fetch_market_prices()
        metal_data = data.get(metal)

        if not isinstance(metal_data, dict):
            logger.error(
                "Missing %s data. Provider keys: %s",
                metal,
                list(data.keys())
            )

            return jsonify({
                "available": False,
                "metal": metal,
                "error": (
                    f"{metal.title()} rate was not found in the "
                    "provider response. Check the Flask terminal."
                )
            }), 502

        result = dict(metal_data)
        result["available"] = True
        result["metal"] = metal
        result["updated_at"] = (
            original.get("timestamp")
            or data.get("timestamp")
            or datetime.now(timezone.utc).isoformat()
        )

        return jsonify(result), 200

    except requests.Timeout:
        logger.exception("OroPocket request timed out.")

        return jsonify({
            "available": False,
            "metal": metal,
            "error": "The rate provider timed out."
        }), 504

    except requests.RequestException:
        logger.exception("Could not fetch OroPocket rates.")

        return jsonify({
            "available": False,
            "metal": metal,
            "error": (
                "Rate provider request failed. Check connectivity "
                "and API access."
            )
        }), 502

    except (ValueError, TypeError):
        logger.exception("Invalid OroPocket response.")

        return jsonify({
            "available": False,
            "metal": metal,
            "error": "The rate provider returned invalid data."
        }), 502

    except Exception:
        logger.exception("Unexpected rate-provider error.")

        return jsonify({
            "available": False,
            "metal": metal,
            "error": "Unexpected error while fetching market rates."
        }), 500


@app.route("/api/gold-rate", methods=["GET"])
def gold_rate():
    return get_metal_rate("gold")


@app.route("/api/silver-rate", methods=["GET"])
def silver_rate():
    return get_metal_rate("silver")


# --------------------------------------------------
# Run Flask
# --------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))

    app.run(
        host="127.0.0.1",
        port=port,
        debug=True
    )
