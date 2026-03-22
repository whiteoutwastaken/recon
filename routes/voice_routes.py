import os
import re
from openai import OpenAI
from flask import Blueprint, jsonify, request, send_file
from database import get_db

voice_bp = Blueprint("voice", __name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


def _format_for_voice(text: str) -> str:
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"#+\s", "", text)
    text = re.sub(r"`(.*?)`", r"\1", text)
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
    text = re.sub(r"^\s*[-•*]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _shorten_for_voice(text: str, max_chars: int = 800) -> str:
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_period = truncated.rfind(".")
    return truncated[:last_period + 1] if last_period > max_chars // 2 else truncated + "..."


@voice_bp.route("/voice/query", methods=["POST"])
def voice_query():
    data = request.get_json() or {}
    query = data.get("query") or data.get("question", "")
    if not query:
        return jsonify({"response": "Please provide a question."})
    try:
        from agents.orchestrator import run_orchestrator
        result = run_orchestrator(query)
        answer = _shorten_for_voice(_format_for_voice(result["answer"]))
    except ImportError:
        answer = "The intelligence backend is not ready yet."
    return jsonify({"response": answer})


@voice_bp.route("/voice/patterns", methods=["GET", "POST"])
def voice_patterns():
    conn = get_db()
    rows = conn.execute("SELECT * FROM patterns ORDER BY confidence DESC LIMIT 3").fetchall()
    conn.close()
    if not rows:
        return jsonify({"response": "No competitive patterns have been detected yet."})
    lines = [
        f"Pattern {i+1}: {row['description']} Confidence: {int(row['confidence'] * 100)} percent. Prediction: {row['prediction']}"
        for i, row in enumerate(rows)
    ]
    return jsonify({"response": " ".join(lines)})


@voice_bp.route("/voice/compare", methods=["POST"])
def voice_compare():
    data = request.get_json() or {}
    comp_a = data.get("comp_a", "")
    comp_b = data.get("comp_b", "")
    dimension = data.get("dimension", "overall strategy")
    if not comp_a or not comp_b:
        return jsonify({"response": "Please specify two competitors to compare."})
    try:
        from agents.orchestrator import run_orchestrator
        result = run_orchestrator(f"Compare {comp_a} and {comp_b} on {dimension}")
        answer = _shorten_for_voice(_format_for_voice(result["answer"]))
    except ImportError:
        answer = "The comparison agent is not ready yet."
    return jsonify({"response": answer})


@voice_bp.route("/voice/briefing", methods=["GET", "POST"])
def voice_briefing():
    conn = get_db()
    events = conn.execute(
        """SELECT e.*, c.name as company_name FROM events e
           JOIN competitors c ON e.competitor_id = c.id
           ORDER BY e.date DESC LIMIT 10"""
    ).fetchall()
    patterns = conn.execute("SELECT * FROM patterns ORDER BY confidence DESC LIMIT 2").fetchall()
    conn.close()

    if not events:
        return jsonify({"response": "No data available for briefing yet.", "text": ""})

    events_text = "\n".join([f"- {dict(e)['company_name']}: {dict(e)['title']} ({dict(e)['date']})" for e in events])
    patterns_text = "\n".join([f"- {dict(p)['description']} (prediction: {dict(p)['prediction']})" for p in patterns]) or "No patterns detected yet."

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=512,
        messages=[
            {
                "role": "system",
                "content": "Write a 60-second spoken competitive intelligence briefing for a VP of Strategy. Use short, clear sentences. No markdown. No bullet points. Start with: Good morning. Here is your Recon briefing. Cover key developments, then any pattern alerts, then one prediction.",
            },
            {
                "role": "user",
                "content": f"Recent developments:\n{events_text}\n\nPattern alerts:\n{patterns_text}",
            },
        ],
    )

    briefing_text = response.choices[0].message.content.strip()

    # Generate audio via edge-tts
    audio_url = None
    try:
        import asyncio
        import edge_tts

        async def _synthesize(text, path):
            communicate = edge_tts.Communicate(text, voice="en-US-GuyNeural")
            await communicate.save(path)

        audio_path = "static/briefing.mp3"
        os.makedirs("static", exist_ok=True)
        asyncio.run(_synthesize(briefing_text, audio_path))
        audio_url = "/api/voice/briefing-audio"
    except Exception as e:
        print(f"TTS generation failed: {e}")

    return jsonify({"response": briefing_text, "text": briefing_text, "audio_url": audio_url})


@voice_bp.route("/voice/briefing-audio", methods=["GET"])
def briefing_audio():
    audio_path = "static/briefing.mp3"
    if not os.path.exists(audio_path):
        return jsonify({"error": "No briefing audio generated yet"}), 404
    return send_file(audio_path, mimetype="audio/mpeg")