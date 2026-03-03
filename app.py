from flask import Flask, render_template, request, redirect, session, url_for, flash
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import json
import os
from functools import wraps
from collections import defaultdict
import time
from mysql.connector import Error

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "supersecretkey")

# ----------------------------
# Database connection
# ----------------------------
db = None
for i in range(10):
    try:
        db = mysql.connector.connect(
            host=os.environ.get("MYSQL_HOST", "sanreach_db"),
            user=os.environ.get("MYSQL_USER", "flaskuser"),
            password=os.environ.get("MYSQL_PASSWORD", "Tsanjay@212"),
            database=os.environ.get("MYSQL_DB", "sanreach")
        )
        print("✅ DB connected")
        break
    except Error as e:
        print(f"⚠️ DB connection failed, retrying... ({i+1}/10)")
        time.sleep(3)

if db is None:
    raise Exception("❌ Could not connect to the database after 10 retries")

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
# Dashboard Route
# ----------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT DATE(sent_at) as day, dest, message, status, sent_at
        FROM sms_logs
        WHERE user_id = %s
        ORDER BY sent_at DESC
    """, (session["user_id"],))
    sms_data = cursor.fetchall()
    day_wise = defaultdict(list)
    for row in sms_data:
        day_wise[row["day"]].append(row)

    return render_template("dashboard.html", username=session.get("username"), day_wise=day_wise, show_section=None)

# ----------------------------
# Send SMS Route (AJAX enabled)
# ----------------------------
@app.route("/send_sms", methods=["POST"])
@login_required
def send_sms():
    number = request.form.get("number")
    message_text = request.form.get("message")

    api_url = "https://japi.instaalerts.zone/httpapi/JsonReceiver"
    api_key = "A8CtOgAdEUfuWjFLlvwAOQ=="

    payload = {
        "ver": "1.0",
        "key": api_key,
        "encrypt": "0",
        "messages": [{"dest": [number], "text": message_text, "send": "KARIXM","vp":30,"cust_ref":"cust_ref","lang":"PM"}]
    }

    headers = {"Content-Type": "application/json"}
    status = "Failed"
    message_flash = ""

    try:
        response = requests.post(api_url, headers=headers, data=json.dumps(payload))
        if response.status_code == 200:
            status = "Sent"
            message_flash = "✅ SMS sent successfully!"
        else:
            status = f"Error: {response.text}"
            message_flash = f"⚠️ Failed to send SMS: {response.text}"
    except Exception as e:
        status = f"Exception: {str(e)}"
        message_flash = f"⚠️ Error sending SMS: {str(e)}"

    # Log SMS
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO sms_logs (user_id, dest, message, status) VALUES (%s, %s, %s, %s)",
        (session["user_id"], number, message_text, status)
    )
    db.commit()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return {"status": status, "message": message_flash}

    flash(message_flash)
    return redirect(url_for("dashboard"))

# ----------------------------
# Reports Route (date-range)
# ----------------------------
@app.route("/reports")
@login_required
def reports():
    start_date = request.args.get("start")
    end_date = request.args.get("end")
    cursor = db.cursor(dictionary=True)

    if start_date and end_date:
        cursor.execute("""
            SELECT DATE(sent_at) as day, dest, message, status, sent_at
            FROM sms_logs
            WHERE user_id=%s AND DATE(sent_at) BETWEEN %s AND %s
            ORDER BY sent_at DESC
        """, (session["user_id"], start_date, end_date))
    else:
        cursor.execute("""
            SELECT DATE(sent_at) as day, dest, message, status, sent_at
            FROM sms_logs
            WHERE user_id=%s
            ORDER BY sent_at DESC
        """, (session["user_id"],))

    sms_data = cursor.fetchall()
    day_wise = defaultdict(list)
    for row in sms_data:
        day_wise[row["day"]].append(row)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        # Return only table HTML
        table_html = ""
        for day, logs in day_wise.items():
            table_html += f'<div class="card" style="margin-bottom:10px;"><h4>{day}</h4><table style="width:100%; border-collapse: collapse;"><thead><tr style="background: rgba(255,255,255,0.2);"><th>Recipient</th><th>Message</th><th>Status</th><th>Sent At</th></tr></thead><tbody>'
            for sms in logs:
                table_html += f'<tr style="background: rgba(255,255,255,0.05);"><td>{sms["dest"]}</td><td>{sms["message"]}</td><td>{sms["status"]}</td><td>{sms["sent_at"]}</td></tr>'
            table_html += "</tbody></table></div>"
        if not day_wise:
            table_html = "<p>No SMS records found for this date range.</p>"
        return table_html

    return render_template("dashboard.html", day_wise=day_wise, username=session.get("username"), show_section="report")

# ----------------------------
# Run Flask
# ----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)