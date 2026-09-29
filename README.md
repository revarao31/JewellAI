# ✦ JewellAI — Smart Jewellery Assistant

> An AI-powered jewellery chatbot that helps users understand gold, silver, diamonds, jewellery pricing, buying guidance, and live metal rates.

JewellAI is a jewellery-focused AI assistant built with a **Flask backend, Gemini AI, and a responsive React-based chatbot interface**. It combines conversational AI with real-time gold and silver rates from **OroPocket** and includes a jewellery price calculator.

---

## ✨ Features

### 🤖 AI Jewellery Assistant

Ask natural-language questions about:

* Gold and silver
* 18K, 22K and 24K gold
* BIS Hallmark and HUID
* Diamond 4Cs
* Jewellery buying guidance
* Making charges and GST
* Jewellery care
* Jewellery trends and designs

### 🪙 Live Gold & Silver Rates

JewellAI retrieves published metal rates from **OroPocket** instead of generating or guessing current prices.

The assistant can provide:

* Gold rate per gram
* Silver rate per gram
* Buy and sell rates
* Rate source
* Latest available update time

It can also calculate the approximate raw metal value for queries such as:

> What is the price of 50 grams of gold today?

> What is the price of 1 kg of silver today?

### 🧮 Jewellery Price Calculator

The built-in calculator estimates jewellery cost using:

* Weight
* Gold rate
* Making charges
* GST
* Estimated final amount

The calculator is intended as an estimate and does not replace a jeweller's final invoice.

### 💬 Gemini-Powered Conversations

JewellAI uses Google's Gemini API for general jewellery-related questions.

The backend includes retry and fallback handling for temporary model availability issues, helping the chatbot remain usable during temporary API failures.

### 📱 Responsive Chat Interface

The frontend is designed as a chatbot rather than an e-commerce website and works across:

* Desktop
* Laptop
* Tablet
* Mobile

---

## 🛠️ Tech Stack

### Frontend

* HTML5
* CSS3
* JavaScript
* React 18
* Babel
* Marked
* DOMPurify

### Backend

* Python
* Flask
* Flask-CORS
* Requests
* python-dotenv
* Google Gemini API

### Data

* OroPocket API for published gold and silver rates

### Development

* Git
* GitHub
* VS Code

---

## 📁 Project Structure

```text
JewellAI/
│
├── backend/
│   ├── app.py
│   ├── requirements.txt
│   └── venv/                 # Local only, not committed
│
├── frontend/
│   └── index.html
│
├── .gitignore
└── README.md
```

---

## 🚀 Run Locally

### 1. Clone the repository

```bash
git clone https://github.com/revarao31/JewellAI.git
cd JewellAI
```

### 2. Create and activate a virtual environment

Windows:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Configure environment variables

Create:

```text
backend/.env
```

Add your Gemini configuration:

```env
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.8-flash
PORT=5000
```

**Never commit `.env` to GitHub.**

### 5. Start JewellAI

```powershell
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

---

## 🔌 API Endpoints

| Method | Endpoint           | Purpose                                 |
| ------ | ------------------ | --------------------------------------- |
| GET    | `/`                | JewellAI chatbot interface              |
| GET    | `/api/health`      | Backend and Gemini configuration status |
| GET    | `/api/gold-rate`   | Published live gold rate                |
| GET    | `/api/silver-rate` | Published live silver rate              |
| POST   | `/api/chat`        | Gemini-powered jewellery conversation   |
| POST   | `/api/calculate`   | Jewellery price estimation              |

---

## 🔐 Security

JewellAI keeps the Gemini API key on the backend.

The project excludes sensitive/local files using `.gitignore`:

```text
.env
venv/
__pycache__/
*.pyc
```

The Gemini API key should **never** be placed directly inside frontend code or committed to GitHub.

---

## 💡 Example Questions

Try asking JewellAI:

```text
What's the gold price today?

What's the silver price today?

What is the price of 50 grams of gold today?

What is the price of 1 kg of silver today?

What is the difference between 18K, 22K and 24K gold?

What should I check before buying gold jewellery?

What is BIS Hallmark and HUID?

Explain the 4Cs of diamonds.

How are jewellery making charges calculated?
```

---

## ⚠️ Rate & Pricing Disclaimer

Gold and silver rates shown by JewellAI are based on the published data retrieved from **OroPocket**.

The displayed metal rate should not automatically be interpreted as a specific 22K or 24K jewellery rate.

The final price of jewellery may vary depending on:

* Purity
* Weight
* Making charges
* GST
* Stone/diamond charges
* Jeweller-specific charges
* Other applicable costs

Always verify the final price and invoice with the jeweller before making a purchase.

---

## 🎯 Project Goal

JewellAI aims to make jewellery-related information easier to understand through a conversational AI experience while combining AI assistance with real-time metal-rate information and practical jewellery calculations.

---

## 👩‍💻 Author

**Reva Rao**

MCA Student | AI & Full-Stack Development Enthusiast

GitHub:
https://github.com/revarao31

---

## 📄 License

This project is created for educational and portfolio purposes.
