import os
from flask import Flask, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder="static")
CORS(app, resources={r"/api/*": {"origins": "*"}})

from routes.data_routes import data_bp
from routes.agent_routes import agent_bp
from routes.ingest_routes import ingest_bp
from routes.voice_routes import voice_bp

app.register_blueprint(data_bp, url_prefix="/api")
app.register_blueprint(agent_bp, url_prefix="/api")
app.register_blueprint(ingest_bp, url_prefix="/api")
app.register_blueprint(voice_bp, url_prefix="/api")

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.errorhandler(404)
def not_found(e):
    return {"error": "Not found"}, 404

@app.errorhandler(500)
def server_error(e):
    return {"error": "Internal server error", "details": str(e)}, 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)