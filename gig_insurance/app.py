from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import Table, TableStyle
import os
from datetime import datetime
app = Flask(__name__)
app.secret_key = "supersecretkey"   # Required for sessions


# ---------------- DATABASE SETUP ----------------
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fullname TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    role TEXT DEFAULT 'user'
)
""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS claims(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        claim_type TEXT,
        description TEXT,
        amount INTEGER,
        status TEXT DEFAULT 'Pending'
    )
  """)
    conn.commit()
    conn.close()

init_db()
# ------------------------------------------------


@app.route("/")
def home():
    return render_template("home.html")


# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        fullname = request.form.get("fullname")
        email = request.form.get("email")
        password = request.form.get("password")

        try:
            conn = sqlite3.connect("database.db")
            cursor = conn.cursor()
            cursor.execute("""INSERT INTO users (fullname, email, password, role) 
            VALUES (?, ?, ?, ?)
            """,(fullname, email, password, "user"))
            conn.commit()
            conn.close()

            return redirect(url_for("login"))

        except:
            return "Email already exists!"

    return render_template("register.html")


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
        user = cursor.fetchone()
        conn.close()

        if user:
          session["user_id"] = user[0]
          session["user_name"] = user[1]
          session["role"] = user[4]   # VERY IMPORTANT
          return redirect(url_for("dashboard"))
        else:
            return "Invalid credentials"

    return render_template("login.html")


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template("dashboard.html", name=session["user_name"])


@app.route("/risk", methods=["GET", "POST"])
def risk_assessment():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        try:
            age = int(request.form.get("age", 0))
            experience = int(request.form.get("experience", 0))
            job_type = int(request.form.get("job_type", 0))
            hours = int(request.form.get("working_hours", 0))
        except:
            return "Invalid Input"

        risk_score = min(100, (hours * 5 + job_type * 10 - experience * 2))

        if risk_score < 30:
            risk_level = "Low"
            premium = 500
            coverage = 200000
        elif risk_score < 60:
            risk_level = "Medium"
            premium = 1000
            coverage = 400000
        else:
            risk_level = "High"
            premium = 2000
            coverage = 800000

        return render_template("policy.html",
                               risk_level=risk_level,
                               premium=premium,
                               coverage=coverage)

    return render_template("risk_assessment.html")
@app.route("/policy")
def policy():
    return render_template("policy.html")

@app.route("/download_policy")
def download_policy():

    if "user_id" not in session:
        return redirect(url_for("login"))

    filename = "policy.pdf"
    filepath = os.path.join("static", filename)

    doc = SimpleDocTemplate(filepath, pagesize=A4)
    elements = []

    styles = getSampleStyleSheet()

    elements.append(Paragraph("<b>InsureAI - Policy Document</b>", styles["Title"]))
    elements.append(Spacer(1, 20))

    elements.append(Paragraph(f"Policy Holder: {session['user_name']}", styles["Normal"]))
    elements.append(Paragraph("Risk Level: Medium", styles["Normal"]))
    elements.append(Paragraph("Monthly Premium: ₹1000", styles["Normal"]))
    elements.append(Paragraph("Coverage Amount: ₹400000", styles["Normal"]))
    elements.append(Paragraph(f"Issue Date: {datetime.now().strftime('%d-%m-%Y')}", styles["Normal"]))

    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Benefits:", styles["Heading2"]))
    elements.append(Paragraph("- Accident Coverage", styles["Normal"]))
    elements.append(Paragraph("- Income Protection", styles["Normal"]))
    elements.append(Paragraph("- Medical Support", styles["Normal"]))

    doc.build(elements)

    return redirect(url_for("static", filename=filename))

@app.route("/claim", methods=["GET", "POST"])
def claim():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        claim_type = request.form.get("claim_type")
        description = request.form.get("description")
        amount = request.form.get("amount")

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO claims (user_id, claim_type, description, amount) VALUES (?, ?, ?, ?)",
                       (session["user_id"], claim_type, description, amount))
        conn.commit()
        conn.close()

        return redirect(url_for("view_claims"))

    return render_template("claim.html")

@app.route("/view_claims")
def view_claims():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT claim_type, description, amount, status FROM claims WHERE user_id=?",
                   (session["user_id"],))
    claims = cursor.fetchall()
    conn.close()

    return render_template("view_claims.html", claims=claims)
# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

#-------------------admin routes-------------------
@app.route("/admin")
def admin():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        return "Access Denied"

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT claims.id, users.fullname, claims.claim_type,
               claims.description, claims.amount, claims.status
        FROM claims
        JOIN users ON claims.user_id = users.id
    """)

    claims = cursor.fetchall()
    conn.close()

    return render_template("admin.html", claims=claims)
@app.route("/update_claim/<int:claim_id>/<string:new_status>")
def update_claim(claim_id, new_status):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        return "Access Denied"

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("UPDATE claims SET status=? WHERE id=?",
                   (new_status, claim_id))

    conn.commit()
    conn.close()

    return redirect(url_for("admin"))
@app.route("/create_admin")
def create_admin():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO users (fullname, email, password, role)
    VALUES (?, ?, ?, ?)
    """, ("Admin", "admin@gmail.com", "admin123", "admin"))

    conn.commit()
    conn.close()

    return "Admin Created Successfully"

if __name__ == "__main__":
    app.run(debug=True)