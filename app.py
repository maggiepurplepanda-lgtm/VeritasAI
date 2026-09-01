import json
import os
from datetime import datetime

import httpx
from flask import Flask, render_template, request, jsonify, redirect, url_for


def load_env_file(path=None):
    """Load environment variables from a .env file without external dependencies."""
    env_path = path or os.path.join(os.path.dirname(__file__), '.env')
    if not os.path.exists(env_path):
        return

    with open(env_path, 'r', encoding='utf-8') as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue

            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"\'')
            os.environ.setdefault(key, value)


load_env_file()

app = Flask(__name__)

# File store for persistent witness profiles
DB_FILE = 'witnesses.json'

# Store session analytics logs and speech transcripts in memory
session_telemetry_logs = []
session_transcripts = []

# Load Gemini configuration from environment variables.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()


def call_gemini_chat(messages, system_prompt=None, temperature=0.7, max_tokens=350):
    """Call Gemini directly while ignoring inherited proxy settings."""
    for proxy_var in (
        "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
        "http_proxy", "https_proxy", "all_proxy",
        "SOCKS_PROXY", "socks_proxy", "GRPC_PROXY", "grpc_proxy",
        "FTP_PROXY", "ftp_proxy"
    ):
        os.environ.pop(proxy_var, None)

    contents = []
    for message in messages:
        contents.append({
            "role": "model" if message.get("role") == "assistant" else "user",
            "parts": [{"text": message.get("content", "")}],
        })

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system_prompt:
        payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

    with httpx.Client(proxy=None, trust_env=False, timeout=60) as client:
        response = client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json=payload,
        )
        response.raise_for_status()
        body = response.json()

    candidates = body.get("candidates", [])
    if not candidates:
        raise ValueError("Gemini returned no candidates.")

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "\n".join(part.get("text", "") for part in parts if part.get("text"))
    return text.strip()

# Helper functions for Witness DB Management
def load_witness_db():
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def save_witness_db(db):
    with open(DB_FILE, 'w') as f:
        json.dump(db, f, indent=4)

# --- PAGE ROUTING ---

@app.route('/')
def landing():
    """Serves the main presentation landing page."""
    return render_template('landing.html')

@app.route('/app')
def main_app():
    """Redirect the legacy app route to the new dashboard page."""
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    """Serves the dashboard landing page."""
    return render_template('index.html')

@app.route('/assistant')
def assistant():
    """Serves the dedicated chatbot page."""
    return render_template('chatbot.html')

@app.route('/witnesses')
def witness_page():
    """Serves the historical witness profiles page."""
    return render_template('witness.html')

@app.route('/post')
def post_page():
    """Serves the deposition brief page."""
    return render_template('post.html')

# --- TELEMETRY & TRANSCRIPT ENDPOINTS ---

@app.route('/api/telemetry', methods=['POST'])
def receive_telemetry():
    """Receives live telemetry frames from the browser engine."""
    data = request.get_json()
    if data:
        data['server_timestamp'] = datetime.now().isoformat()
        session_telemetry_logs.append(data)
        return jsonify({"status": "success", "logged_frames": len(session_telemetry_logs)}), 200
    return jsonify({"status": "error", "message": "No data received"}), 400

@app.route('/api/transcript', methods=['POST'])
def receive_transcript():
    """Receives final speech transcription snippets from WebSpeech API."""
    data = request.get_json()
    if data:
        data['server_timestamp'] = datetime.now().isoformat()
        session_transcripts.append(data)
        return jsonify({"status": "success", "logged_transcripts": len(session_transcripts)}), 200
    return jsonify({"status": "error", "message": "No transcript data"}), 400

@app.route('/api/session-summary', methods=['GET'])
def get_session_summary():
    """Returns aggregated session statistics for reporting."""
    if not session_telemetry_logs:
        return jsonify({"message": "No telemetry recorded yet"}), 200

    anomalies = [log for log in session_telemetry_logs if log.get('status') == 'HIGH_STRESS_ANOMALY']
    return jsonify({
        "total_frames_logged": len(session_telemetry_logs),
        "total_high_stress_anomalies": len(anomalies),
        "total_transcripts_logged": len(session_transcripts),
        "anomaly_timestamps": [a.get('timestamp') for a in anomalies]
    }), 200

# --- HISTORICAL WITNESS PROFILING ENDPOINTS ---

@app.route('/api/witnesses', methods=['GET'])
def get_witnesses():
    """Returns all stored witness profiles."""
    db = load_witness_db()
    return jsonify(db)

@app.route('/api/witness/save-session', methods=['POST'])
def save_witness_session():
    """Saves session biometric averages to a historical witness profile."""
    data = request.get_json() or {}
    witness_name = data.get('name', '').strip()
    session_data = data.get('session_data')

    if not witness_name or not session_data:
        return jsonify({"error": "Missing witness name or session data"}), 400

    db = load_witness_db()

    if witness_name not in db:
        db[witness_name] = {
            "total_sessions": 0,
            "historical_averages": {
                "avg_ear": 0.0,
                "blink_rate_ppm": 0.0,
                "kinetic_energy": 0.0,
                "head_drop": 0.0,
                "shoulder_angle": 0.0
            },
            "sessions": []
        }

    profile = db[witness_name]
    profile["sessions"].append(session_data)
    profile["total_sessions"] += 1

    n = profile["total_sessions"]
    hist = profile["historical_averages"]

    hist["avg_ear"] = round(((hist["avg_ear"] * (n - 1)) + session_data.get("avg_ear", 0)) / n, 2)
    hist["blink_rate_ppm"] = round(((hist["blink_rate_ppm"] * (n - 1)) + session_data.get("blink_rate_ppm", 0)) / n, 1)
    hist["kinetic_energy"] = round(((hist["kinetic_energy"] * (n - 1)) + session_data.get("kinetic_energy", 0)) / n, 2)
    hist["head_drop"] = round(((hist["head_drop"] * (n - 1)) + session_data.get("head_drop", 0)) / n, 2)
    hist["shoulder_angle"] = round(((hist["shoulder_angle"] * (n - 1)) + session_data.get("shoulder_angle", 0)) / n, 1)

    save_witness_db(db)
    return jsonify({"status": "success", "profile": profile}), 200

# --- GEMINI AI ENDPOINTS ---

@app.route('/api/chat', methods=['POST'])
def chat_with_gemini():
    """Proxies user queries to Gemini with live deposition telemetry context."""
    user_data = request.get_json() or {}
    user_message = user_data.get("message", "")

    if not user_message:
        return jsonify({"error": "Empty message"}), 400
    if not GEMINI_API_KEY:
        return jsonify({"error": "GEMINI_API_KEY is not configured on the server."}), 503

    total_frames = len(session_telemetry_logs)
    high_stress_count = sum(1 for log in session_telemetry_logs if log.get('status') == 'HIGH_STRESS_ANOMALY')
    latest_log = session_telemetry_logs[-1] if session_telemetry_logs else {}
    recent_speech = [t.get('text') for t in session_transcripts[-3:]]

    system_instruction = (
        "You are VeritasAI Legal Deposition Assistant. You analyze real-time biometrics, behavioral "
        "telemetry, kinetic posture deviations, and speech transcripts during legal depositions. "
        "Answer concisely, directly, and professionally.\n"
        f"CURRENT SESSION CONTEXT:\n"
        f"- Total Recorded Frames: {total_frames}\n"
        f"- High Stress Anomalies: {high_stress_count}\n"
        f"- Latest Stress Z-Score: {latest_log.get('anomaly_score', 0)}\n"
        f"- Latest Posture Status: {latest_log.get('posture_status', 'UNKNOWN')}\n"
        f"- Total Blinks: {latest_log.get('blinks', 0)}\n"
        f"- Recent Speech Transcripts: {' | '.join(recent_speech) if recent_speech else 'None'}"
    )

    try:
        reply = call_gemini_chat(
            messages=[{"role": "user", "content": user_message}],
            system_prompt=system_instruction,
            temperature=0.7,
            max_tokens=350,
        )
        if not reply:
            return jsonify({"response": "I’m ready to help, but Gemini did not return any final text for this prompt."}), 200

        return jsonify({"response": reply}), 200

    except Exception as e:
        return jsonify({"error": f"Gemini API error: {str(e)}"}), 500

@app.route('/api/generate-insight', methods=['POST'])
def generate_tactical_insight():
    """Generates real-time cross-examination tactics based on recent telemetry buffer."""
    if not GEMINI_API_KEY:
        return jsonify({"error": "GEMINI_API_KEY not configured."}), 503

    recent_buffer = session_telemetry_logs[-300:] if len(session_telemetry_logs) >= 300 else session_telemetry_logs
    if not recent_buffer:
        return jsonify({"insight": "Insufficient telemetry data collected to generate insights."}), 200

    avg_stress = sum(f.get('anomaly_score', 0) for f in recent_buffer) / len(recent_buffer)
    recent_transcripts = [t.get('text') for t in session_transcripts[-5:]]

    prompt = (
        f"Analyze this recent 30-second deposition telemetry window:\n"
        f"- Average Stress Score: {avg_stress:.2f}\n"
        f"- Recent Speech: {' '.join(recent_transcripts) if recent_transcripts else 'No speech recorded.'}\n\n"
        f"Provide 2 direct, high-impact tactical cross-examination recommendations for questioning counsel."
    )

    try:
        insight = call_gemini_chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="You are an expert trial strategist providing real-time trial tips.",
            temperature=0.5,
            max_tokens=250,
        )
        return jsonify({"insight": insight or "No tactical insight was returned by Gemini."}), 200
    except Exception as e:
        return jsonify({"error": f"Gemini API error: {str(e)}"}), 500

@app.route('/api/generate-brief', methods=['POST'])
def generate_deposition_brief():
    """Compiles whole-session telemetry and transcripts into a formal trial brief."""
    if not GEMINI_API_KEY:
        return jsonify({"error": "GEMINI_API_KEY not configured."}), 503

    if not session_telemetry_logs:
        return jsonify({"brief": "No telemetry recorded during this session."}), 200

    total_frames = len(session_telemetry_logs)
    anomalies = [log for log in session_telemetry_logs if log.get('status') == 'HIGH_STRESS_ANOMALY']
    transcripts = [f"[{t.get('timestamp')}] {t.get('text')}" for t in session_transcripts]

    prompt = (
        f"Generate a concise post-deposition credibility brief based on the following session summary:\n"
        f"- Total Frames Analyzed: {total_frames}\n"
        f"- Total High Stress Anomalies Detected: {len(anomalies)}\n"
        f"- Transcript Entries Logged: {len(transcripts)}\n"
        f"- Full Transcript Stream:\n" + "\n".join(transcripts) + "\n\n"
        f"Include Key Anomaly Events, Speech Discrepancies, and Trial Preparedness Recommendations."
    )

    try:
        brief = call_gemini_chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="You are a senior trial consultant preparing a formal post-deposition memorandum.",
            temperature=0.4,
            max_tokens=500,
        )
        return jsonify({"brief": brief or "No deposition brief was returned by Gemini."}), 200
    except Exception as e:
        return jsonify({"error": f"Gemini API error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)