from flask import Flask, render_template, request, redirect, session, url_for, flash
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import json
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "supersecretkey")

# ----------------------------
# Database connection
# ----------------------------
db = mysql.connector.connect(
    host=os.environ.get("MYSQL_HOST", "sanreach_db"),
    user=os.environ.get("MYSQL_USER", "flaskuser"),
    password=os.environ.get("MYSQL_PASSWORD", "Tsanjay@212"),
    database=os.environ.get("MYSQL_DB", "sanreach")
)

# ----------------------------
# Login Required Decorator
# ----------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# ----------------------------
# Auth Routes
# ----------------------------
@app.route("/", methods=["GET"])
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    message = ""
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cursor.fetchone()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("dashboard"))
        else:
            message = "Invalid credentials"

    return render_template("auth.html", message=message)

@app.route("/register", methods=["POST"])
def register():
    username = request.form["username"]
    email = request.form["email"]
    password = request.form["password"]
    hashed_password = generate_password_hash(password)

    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO users (username,email,password) VALUES (%s,%s,%s)",
        (username, email, hashed_password)
    )
    db.commit()
    flash("User registered successfully!", "success")
    return redirect(url_for("login"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ----------------------------
# Dashboard
# ----------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", username=session.get("username"))

# ----------------------------
# Send SMS Route
# ----------------------------
@app.route("/send_sms", methods=["POST"])
@login_required
def send_sms():
    number = request.form.get("number")
    message_text = request.form.get("message")

    api_url = "https://japi.instaalerts.zone/httpapi/JsonReceiver"
    api_key = "A8CtOgAdEUfuWjFLlvwAOQ=="  # <-- Replace with your actual API key

    payload = {
        "ver": "1.0",
        "key": api_key,
        "encrypt": "0",
        "messages": [
            {
                "dest": [number],
                "text": message_text,
                "send": "KARIXM",
                "vp": 30,
                "cust_ref": "cust_ref",
                "lang": "PM"
            }
        ]
    }

    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(api_url, headers=headers, data=json.dumps(payload))
        if response.status_code == 200:
            flash("SMS sent successfully!", "success")
        else:
            flash(f"Failed to send SMS: {response.text}", "error")
    except Exception as e:
        flash(f"Error sending SMS: {str(e)}", "error")

    return redirect(url_for("dashboard"))

# ----------------------------
# Placeholder Reports Route
# ----------------------------
@app.route("/reports")
@login_required
def reports():
    flash("Reports feature coming soon!", "info")
    return redirect(url_for("dashboard"))

# ----------------------------
# Run Flask
# ----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
