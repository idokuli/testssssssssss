import os, secrets, subprocess, sys, multiprocessing
from flask import Flask, render_template
from routes.s3_routes import s3_bp
from routes.stress_routes import stress_bp

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# Register Blueprints
app.register_blueprint(s3_bp, url_prefix='/bucket')
app.register_blueprint(stress_bp, url_prefix='/stress')

# SSL Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
cert, key = os.path.join(BASE_DIR, 'cert.pem'), os.path.join(BASE_DIR, 'key.pem')

@app.route('/')
def hub():
    return render_template('hub.html', cores=multiprocessing.cpu_count())

@app.route('/health')
def health():
    return {"status": "healthy"}, 200

if __name__ == '__main__':
    from werkzeug.serving import run_simple
    # Ensure certs exist
    if not os.path.exists(cert):
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:4096", "-nodes", 
                       "-out", cert, "-keyout", key, "-days", "365", 
                       "-subj", "/CN=localhost"], check=True)
    
    print("--- 🛰️ HUB ONLINE [HTTPS:443] ---")
    run_simple('127.0.0.1', 443, app, ssl_context=(cert, key))