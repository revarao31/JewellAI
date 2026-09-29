import os
import re
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from google import genai
from google.genai import types

load_dotenv()

app = Flask(__name__, static_folder="../frontend", static_url_path="")
CORS(app)

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

# Gemini can temporarily return 503 when a model is under heavy demand.
# Keep the primary model first, then use stable fallback models.
FALLBACK_MODELS = [
    MODEL_NAME,
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
]

if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY is missing in .env")

client = genai.Client(api_key=API_KEY)

RATE_URL = "https://api.oropocket.com/public/prices"

SYSTEM_INSTRUCTION = """
You are JewellAI, a professional and friendly Smart Jewellery Assistant.

Help customers with:
- Gold and silver
- 22K, 24K and 18K purity
- BIS Hallmark
- Diamonds and the 4Cs
- Jewellery buying guidance
- Making charges and GST
- Jewellery care
- Wedding and occasion jewellery
- Jewellery trends

Never invent current prices.
For current gold/silver prices, the application handles the live-rate request separately.
Do not call a generic provider rate a 22K or 24K rate unless the supplied data explicitly says so.

Keep responses concise, friendly, practical and conversational.
"""


def get_live_prices():
    try:
        response = requests.get(RATE_URL, timeout=10)
        response.raise_for_status()
        data = response.json()

        # The currently working OroPocket response format is:
        # {
        #   "gold": {
        #       "buy": number,
        #       "sell": number
        #   },
        #   "silver": {
        #       "buy": number,
        #       "sell": number
        #   },
        #   "timestamp": ...
        # }

        # OroPocket returns the metals inside the "data" object.
        payload = data.get("data", data)

        gold = payload.get("gold") or payload.get("Gold") or {}
        silver = payload.get("silver") or payload.get("Silver") or {}

        if not isinstance(gold, dict):
            gold = {}
        if not isinstance(silver, dict):
            silver = {}

        updated = (
            payload.get("updated_at")
            or payload.get("timestamp")
            or payload.get("last_updated")
        )

        return {
            "gold": {
                "buy": gold.get("buy"),
                "sell": gold.get("sell")
            },
            "silver": {
                "buy": silver.get("buy"),
                "sell": silver.get("sell")
            },
            "updated_at": updated,
            "source": "OroPocket"
        }

    except Exception as e:
        print("LIVE RATE ERROR:", repr(e))
        return None


def is_temporary_gemini_error(error):
    """Return True for errors where retrying another Gemini model is useful."""
    message = str(error).lower()
    temporary_codes = [
        "429",
        "500",
        "502",
        "503",
        "504",
        "unavailable",
        "high demand",
        "resource exhausted",
        "temporarily unavailable",
        "deadline exceeded",
    ]
    return any(code in message for code in temporary_codes)


def generate_gemini_reply(prompt):
    """Generate a normal JewellAI answer with retry + model fallback."""
    import time

    # Avoid duplicate model names if the primary model is already one of the fallbacks.
    models_to_try = list(dict.fromkeys(FALLBACK_MODELS))
    last_error = None

    for index, model in enumerate(models_to_try):
        # Try the current model twice for temporary availability errors.
        for attempt in range(2):
            try:
                print(
                    f"GEMINI REQUEST: model={model}, attempt={attempt + 1}"
                )

                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION
                    )
                )

                reply = (response.text or "").strip()

                if reply:
                    print(f"GEMINI SUCCESS: model={model}")
                    return reply

                last_error = RuntimeError(
                    f"Gemini returned an empty response from {model}"
                )

            except Exception as e:
                last_error = e
                print(
                    f"GEMINI ERROR: model={model}, attempt={attempt + 1}: {repr(e)}"
                )

                # Retry only temporary service/rate-limit errors.
                if not is_temporary_gemini_error(e):
                    raise

                # Short backoff before retrying the same model.
                if attempt == 0:
                    time.sleep(1.5)

        # If this model was temporarily unavailable, move to the next stable model.
        if index < len(models_to_try) - 1:
            print(
                f"GEMINI FALLBACK: switching from {model} to {models_to_try[index + 1]}"
            )

    if last_error:
        raise last_error

    raise RuntimeError("Gemini did not return a response.")


def is_gold_question(text):
    t = (text or "").lower()

    if "gold" not in t and "sona" not in t and "sone" not in t:
        return False

    words = [
        "price", "rate", "today", "current", "live",
        "bhav", "kitna", "kitne", "aaj"
    ]

    return any(word in t for word in words)


def is_silver_question(text):
    t = (text or "").lower()

    if "silver" not in t and "chandi" not in t:
        return False

    words = [
        "price", "rate", "today", "current", "live",
        "bhav", "kitna", "kitne", "aaj"
    ]

    return any(word in t for word in words)


def format_money(value):
    try:
        return f"₹{float(value):,.2f}"
    except (TypeError, ValueError):
        return None


def extract_weight_grams(text):
    """Extract an explicit weight such as 10g, 10 grams, or 0.5 kg.

    Returns None when the user did not provide a weight, so ordinary
    current-rate questions keep their existing response format.
    """
    t = (text or "").lower().replace(",", "")

    # Prefer kg when explicitly written.
    kg_match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:kg|kgs|kilogram|kilograms)\b", t)
    if kg_match:
        return float(kg_match.group(1)) * 1000

    gram_match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*(?:g|gm|gms|gram|grams)\b",
        t,
    )
    if gram_match:
        return float(gram_match.group(1))

    return None


def make_rate_reply(metal, prices, weight_grams=None):
    if not prices:
        return (
            f"💎 I’m currently unable to retrieve the live {metal} rate "
            "from OroPocket. Please try again in a moment."
        )

    data = prices.get(metal.lower(), {})

    buy = data.get("buy")
    sell = data.get("sell")

    if buy is None and sell is None:
        return (
            f"💎 I’m currently unable to retrieve the live {metal} rate "
            "from OroPocket. Please try again in a moment."
        )

    title = "Gold" if metal.lower() == "gold" else "Silver"

    lines = [
        f"💰 **Today's {title} Rate**",
        "",
    ]

    if sell is not None:
        lines.append(f"• Sell rate: **{format_money(sell)}/gram**")
        if weight_grams is not None:
            sell_value = float(sell) * weight_grams
            lines.append(
                f"• {weight_grams:g}g at sell rate: **{format_money(sell_value)}**"
            )

    if buy is not None:
        lines.append(f"• Buy rate: **{format_money(buy)}/gram**")
        if weight_grams is not None:
            buy_value = float(buy) * weight_grams
            lines.append(
                f"• {weight_grams:g}g at buy rate: **{format_money(buy_value)}**"
            )

    lines.extend([
        "",
        "• Source: **OroPocket**",
        "",
        "This is the provider's published rate per gram. "
        "The calculated amount is the raw metal value only; it is not automatically a 22K/24K jewellery price. "
        "Final jewellery pricing can also include purity, making charges, GST and seller charges."
    ])

    return "\n".join(lines)


@app.get("/")
def home():
    return send_from_directory("../frontend", "index.html")


@app.get("/api/health")
def health():
    return jsonify({
        "ok": True,
        "service": "JewellAI",
        "model": MODEL_NAME,
        "gemini_configured": bool(API_KEY)
    })


@app.get("/api/gold-rate")
def gold_rate():
    prices = get_live_prices()

    if not prices:
        return jsonify({
            "available": False,
            "metal": "Gold",
            "message": "Live gold rate is temporarily unavailable."
        }), 503

    gold = prices["gold"]

    if gold["buy"] is None and gold["sell"] is None:
        return jsonify({
            "available": False,
            "metal": "Gold",
            "message": "Live gold rate is temporarily unavailable."
        }), 503

    return jsonify({
        "available": True,
        "metal": "Gold",
        "currency": "INR",
        "unit": "gram",
        "buy_rate_per_gram": gold["buy"],
        "sell_rate_per_gram": gold["sell"],
        "source": prices["source"],
        "updated_at": prices["updated_at"]
    })


@app.get("/api/silver-rate")
def silver_rate():
    prices = get_live_prices()

    if not prices:
        return jsonify({
            "available": False,
            "metal": "Silver",
            "message": "Live silver rate is temporarily unavailable."
        }), 503

    silver = prices["silver"]

    if silver["buy"] is None and silver["sell"] is None:
        return jsonify({
            "available": False,
            "metal": "Silver",
            "message": "Live silver rate is temporarily unavailable."
        }), 503

    return jsonify({
        "available": True,
        "metal": "Silver",
        "currency": "INR",
        "unit": "gram",
        "buy_rate_per_gram": silver["buy"],
        "sell_rate_per_gram": silver["sell"],
        "source": prices["source"],
        "updated_at": prices["updated_at"]
    })


@app.post("/api/chat")
def chat():
    try:
        body = request.get_json(silent=True) or {}
        messages = body.get("messages", [])

        if not messages:
            return jsonify({"error": "No messages provided"}), 400

        last_user_message = ""

        for message in reversed(messages):
            if message.get("role") == "user":
                last_user_message = str(message.get("content", ""))
                break

        # IMPORTANT:
        # Live price questions do NOT go through Gemini.
        # This prevents a Gemini model/API problem from breaking live prices.
        if is_gold_question(last_user_message):
            prices = get_live_prices()
            weight_grams = extract_weight_grams(last_user_message)
            return jsonify({
                "reply": make_rate_reply("Gold", prices, weight_grams)
            })

        if is_silver_question(last_user_message):
            prices = get_live_prices()
            weight_grams = extract_weight_grams(last_user_message)
            return jsonify({
                "reply": make_rate_reply("Silver", prices, weight_grams)
            })

        conversation = []

        for message in messages[-20:]:
            content = str(message.get("content", "")).strip()

            if not content:
                continue

            role = (
                "Customer"
                if message.get("role") == "user"
                else "JewellAI"
            )

            conversation.append(
                f"{role}: {content}"
            )

        prompt = "\n".join(conversation)

        reply = generate_gemini_reply(prompt)

        return jsonify({"reply": reply})

    except Exception as e:
        print("CHAT ERROR:", repr(e))

        return jsonify({
            "error": "JewellAI could not process the request.",
            "details": str(e)
        }), 502


@app.post("/api/calculate")
def calculate():
    try:
        data = request.get_json(silent=True) or {}

        weight = float(
            data.get("weight")
            or data.get("weight_g")
            or 0
        )

        rate = float(
            data.get("rate_per_10g")
            or 0
        )

        making = float(
            data.get("making_percent")
            or data.get("making_charge_percent")
            or 0
        )

        gst = float(
            data.get("gst_percent")
            or 3
        )

        if weight <= 0 or rate <= 0:
            return jsonify({
                "error": "Weight and gold rate must be greater than 0."
            }), 400

        metal_value = weight * (rate / 10)
        making_charge = metal_value * making / 100
        subtotal = metal_value + making_charge
        gst_amount = subtotal * gst / 100
        total = subtotal + gst_amount

        return jsonify({
            "weight": weight,
            "rate_per_10g": rate,
            "metal_value": round(metal_value, 2),
            "making_charge": round(making_charge, 2),
            "gst": round(gst_amount, 2),
            "total_estimate": round(total, 2),
            "gold_value": round(metal_value, 2),
            "making_charges": round(making_charge, 2),
            "subtotal": round(subtotal, 2)
        })

    except (TypeError, ValueError):
        return jsonify({
            "error": "Please enter valid numeric values."
        }), 400


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True
    )
