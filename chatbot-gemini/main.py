from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import os
import requests

# === Dosya yolları ===
DATA_FILE = "data/overrides.json"
CHAT_HISTORY_FILE = "data/chat_history.json"

# === FastAPI uygulaması ===
app = FastAPI()

# === CORS (frontend erişimi için)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Gemini API Ayarları ===
GEMINI_API_KEY = "AIzaSyBtyWOLNw20t7ag5pQYc1mU9WSP0oQJyvE"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

class UserMessage(BaseModel):
    message: str

# === Override verileri
def load_overrides():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_overrides(overrides):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(overrides, f, ensure_ascii=False, indent=4)

def find_override(message, overrides):
    for item in overrides:
        if item["question"].lower() in message.lower():
            return item["answer"]
    return None

# === Kalıcı sohbet geçmişi
def load_chat_history():
    if os.path.exists(CHAT_HISTORY_FILE):
        with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_chat_history(history):
    with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=4)

# === Chatbot endpoint
@app.post("/ask")
def ask_question(user_message: UserMessage):
    message = user_message.message.strip()
    overrides = load_overrides()
    history = load_chat_history()  # 🔹 Geçmişi dosyadan yükle

    # Doğru cevap düzeltmesi
    if message.lower().startswith("doğru cevap bu:"):
        return {"response": "Lütfen 'soru | doğru cevap bu: ...' şeklinde girin."}

    if "| doğru cevap bu:" in message.lower():
        try:
            question_part, correct_answer = message.split("| doğru cevap bu:", 1)
            question = question_part.strip()
            correct_answer = correct_answer.strip()
            overrides.append({
                "question": question,
                "answer": correct_answer
            })
            save_overrides(overrides)
            return {"response": "Yeni cevap kaydedildi."}
        except:
            return {"response": "Hatalı format. 'soru | doğru cevap bu: ...' şeklinde yazılmalı."}

    overridden = find_override(message, overrides)
    if overridden:
        return {"response": overridden}

    # 🔹 Sohbete yeni kullanıcı mesajı ekle
    history.append({"role": "user", "parts": [{"text": message}]})

    try:
        response = requests.post(
            GEMINI_API_URL,
            headers={"Content-Type": "application/json"},
            json={"contents": history}
        )

        if response.status_code == 200:
            data = response.json()
            bot_response = data["candidates"][0]["content"]["parts"][0]["text"]

            # 🔹 Cevapta biçimlendirme düzeltmeleri
            bot_response = bot_response.replace("**", '"').replace("*", ",")
            bot_response = bot_response.replace(" ,", ",").replace(",,", ",").strip()
            bot_response = bot_response.lstrip(",").replace("\n", " ").strip()

            # 🔹 Bot cevabını geçmişe ekle
            history.append({"role": "model", "parts": [{"text": bot_response}]})

            save_chat_history(history)  # 🔹 Geçmişi kaydet
            return {"response": bot_response}
        else:
            return {"response": f"Gemini API hatası: {response.status_code} - {response.text}"}
    except Exception as e:
        return {"response": f"API bağlantı hatası: {str(e)}"}

# === Sohbet geçmişini sıfırlama
@app.post("/reset")
def reset_history():
    save_chat_history([])
    return {"message": "Sohbet geçmişi sıfırlandı."}

# === Yönetim Paneli (admin)
@app.get("/admin/overrides")
def get_overrides():
    return load_overrides()

@app.post("/admin/overrides")
def add_override(item: dict):
    overrides = load_overrides()
    overrides.append(item)
    save_overrides(overrides)
    return {"message": "Eklendi"}

@app.delete("/admin/overrides/{index}")
def delete_override(index: int):
    overrides = load_overrides()
    if 0 <= index < len(overrides):
        overrides.pop(index)
        save_overrides(overrides)
        return {"message": "Silindi"}
    return {"error": "Geçersiz index"}

@app.put("/admin/overrides/{index}")
def update_override(index: int, item: dict):
    overrides = load_overrides()
    if 0 <= index < len(overrides):
        overrides[index] = item
        save_overrides(overrides)
        return {"message": "Güncellendi"}
    return {"error": "Geçersiz index"}
