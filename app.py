
from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import uuid
import random
import time
import os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)
app.secret_key = "finance_secret_key"

DATABASE = "instance/database.db"
# ================= JINJA DATE FILTER =================
@app.template_filter("pretty_date")
def pretty_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d-%m-%Y")
    except:
        return value

# ---------------- DATABASE ----------------
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()

    # USERS TABLE
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            profile_pic TEXT
        )
    """)

    # RESET TOKENS TABLE
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            token TEXT NOT NULL
        )
    """)

    # ✅ ADD THIS (INCOME TABLE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS income (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            source TEXT NOT NULL,
            amount REAL NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()

init_db()

def get_monthly_income(user_id):
    conn = get_db()
    rows = conn.execute("""
        SELECT 
            strftime('%Y', date) AS year,
            strftime('%m', date) AS month,
            SUM(amount) AS total
        FROM income
        WHERE user_id = ?
        GROUP BY year, month
        ORDER BY year, month
    """, (user_id,)).fetchall()
    conn.close()

    result = {}
    for row in rows:
        key = f"{row['year']}-{row['month']}"
        result[key] = row["total"]

    return result


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()
    conn.close()

    return render_template(
        "dashboard.html",
        user=user
    )


# ---------------- DEMO EMAIL FUNCTION (TERMINAL MODE) ----------------
# OTP & reset links will be printed in terminal instead of sending email

def send_email(to, subject, body):
    print("\n========== OTP / RESET MESSAGE ==========")
    print("TO:", to)
    print("SUBJECT:", subject)
    print("MESSAGE:\n", body)
    print("========================================\n")



# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        confirm = request.form["confirm"]

        if password != confirm:
            flash("Passwords do not match")
            return redirect(url_for("register"))

        hashed = generate_password_hash(password)

        try:
            conn = get_db()
            conn.execute(
                "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                (name, email, hashed)
            )
            conn.commit()
            conn.close()
            flash("Registration Successful! Please Login.")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already exists!")
            return redirect(url_for("register"))

    return render_template("register.html")

# ---------------- ADD PROFILE PIC COLUMN (ONE TIME) ----------------
def add_profile_pic_column():
    conn = get_db()
    try:
        conn.execute("ALTER TABLE users ADD COLUMN profile_pic TEXT")
        conn.commit()
    except:
        pass
    conn.close()

add_profile_pic_column()

# ---------------- LOGIN ----------------
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            # Generate OTP
            otp = str(random.randint(100000, 999999))
            session["otp"] = otp
            session["otp_time"] = time.time()
            session["temp_user"] = user["id"]
            session["temp_email"] = user["email"]

            send_email(
                user["email"],
                "Your OTP for Login",
                f"Your OTP is: {otp}\nThis OTP is valid for 2 minutes."
            )

            return redirect(url_for("otp"))

        flash("Invalid email or password")
        return redirect(url_for("login"))

    return render_template("login.html")

# ---------------- OTP VERIFY ----------------
@app.route("/otp", methods=["GET", "POST"])
def otp():
    if "otp" not in session:
        return redirect(url_for("login"))

    otp_value = session["otp"]   # 👈 expose OTP for screen (DEV MODE)

    if request.method == "POST":
        entered_otp = request.form["otp"]

        # OTP expiry: 2 minutes
        if time.time() - session["otp_time"] > 120:
            session.clear()
            flash("OTP expired. Please login again.")
            return redirect(url_for("login"))

        if entered_otp == session["otp"]:
            session["user_id"] = session["temp_user"]
            session.pop("otp")
            session.pop("otp_time")
            session.pop("temp_user")
            session.pop("temp_email")
            return redirect(url_for("dashboard"))

        flash("Invalid OTP")
        return redirect(url_for("otp"))

    return render_template("otp.html", dev_otp=otp_value)

# ---------------- RESEND OTP ----------------
@app.route("/resend-otp")
def resend_otp():
    if "temp_user" not in session or "temp_email" not in session:
        return redirect(url_for("login"))

    # Generate new OTP
    otp = str(random.randint(100000, 999999))
    session["otp"] = otp
    session["otp_time"] = time.time()

    send_email(
        session["temp_email"],
        "Your New OTP",
        f"Your new OTP is: {otp}\nThis OTP is valid for 2 minutes."
    )

    flash("New OTP sent! (Check terminal)")
    return redirect(url_for("otp"))


# ---------------- CHANGE PASSWORD ----------------
@app.route("/change-password", methods=["GET", "POST"])
def change_password():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        old_password = request.form["old_password"]
        new_password = request.form["new_password"]
        confirm_password = request.form["confirm_password"]

        if new_password != confirm_password:
            flash("New passwords do not match!")
            return redirect(url_for("change_password"))

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE id = ?", (session["user_id"],)
        ).fetchone()

        if not check_password_hash(user["password"], old_password):
            conn.close()
            flash("Old password is incorrect!")
            return redirect(url_for("change_password"))

        hashed = generate_password_hash(new_password)
        conn.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (hashed, session["user_id"])
        )
        conn.commit()
        conn.close()

        flash("Password updated successfully!")
        return redirect(url_for("dashboard"))

    # GET request → show form
    return render_template("change_password.html")


# ---------------- FORGOT PASSWORD ----------------
@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        email = request.form["email"]
        token = str(uuid.uuid4())

        conn = get_db()
        conn.execute(
            "INSERT INTO reset_tokens (email, token) VALUES (?, ?)",
            (email, token)
        )
        conn.commit()
        conn.close()

        reset_link = "http://127.0.0.1:5000/reset/" + token

        send_email(
            email,
            "Password Reset",
            f"Click the link to reset your password:\n{reset_link}"
        )

        return render_template("forgot.html", dev_link=reset_link)

    return render_template("forgot.html")



# ---------------- RESET PASSWORD ----------------
@app.route("/reset/<token>", methods=["GET", "POST"])
def reset_password(token):
    conn = get_db()
    record = conn.execute(
        "SELECT * FROM reset_tokens WHERE token = ?", (token,)
    ).fetchone()

    if not record:
        conn.close()
        flash("Invalid or expired link")
        return redirect(url_for("login"))

    if request.method == "POST":
        password = request.form["password"]
        confirm = request.form["confirm"]

        if password != confirm:
            flash("Passwords do not match")
            return redirect(request.url)

        hashed = generate_password_hash(password)

        conn.execute(
            "UPDATE users SET password = ? WHERE email = ?",
            (hashed, record["email"])
        )
        conn.execute(
            "DELETE FROM reset_tokens WHERE token = ?", (token,)
        )
        conn.commit()
        conn.close()

        flash("Password reset successful. Please login.")
        return redirect(url_for("login"))

    conn.close()
    return render_template("reset_password.html")
# ---------------- EDIT PROFILE ----------------
UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/edit-profile", methods=["GET", "POST"])
def edit_profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?", (session["user_id"],)
    ).fetchone()

    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]

        profile_pic = user["profile_pic"]

        if "profile_pic" in request.files:
            file = request.files["profile_pic"]
            if file and file.filename:
                filename = secure_filename(file.filename)
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)
                profile_pic = filename

        try:
            conn.execute(
                "UPDATE users SET name = ?, email = ?, profile_pic = ? WHERE id = ?",
                (name, email, profile_pic, session["user_id"])
            )
            conn.commit()
            flash("Profile updated successfully!")
            return redirect(url_for("dashboard"))

        except sqlite3.IntegrityError:
            flash("Email already in use!")
            return redirect(url_for("edit_profile"))

    conn.close()
    return render_template("edit_profile.html", user=user)



# ---------------- LOGOUT ----------------
@app.route("/logout", methods=["GET", "POST"])
def logout():
    if request.method == "POST":
        session.clear()
        return redirect(url_for("login"))

    return render_template("logout.html")


# ---------------- RUN ----------------
@app.route("/income")
def income_summary():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    incomes = conn.execute(
        "SELECT * FROM income WHERE user_id = ? ORDER BY date DESC LIMIT 5",
        (session["user_id"],)
    ).fetchall()

    total = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM income WHERE user_id = ?",
        (session["user_id"],)
    ).fetchone()[0]

    conn.close()

    # ✅ ADD THIS LINE
    monthly_income = get_monthly_income(session["user_id"])

    return render_template(
        "income_summary.html",
        incomes=incomes,
        total_income=total,
        monthly_income=monthly_income   # ✅ PASS TO TEMPLATE
    )

# @app.route("/income")
# def income_summary():
#     if "user_id" not in session:
#         return redirect(url_for("login"))

#     conn = get_db()

#     incomes = conn.execute(
#         "SELECT * FROM income WHERE user_id = ? ORDER BY date DESC LIMIT 5",
#         (session["user_id"],)
#     ).fetchall()

#     total = conn.execute(
#         "SELECT COALESCE(SUM(amount), 0) FROM income WHERE user_id = ?",
#         (session["user_id"],)
#     ).fetchone()[0]

#     conn.close()

#     return render_template(
#         "income_summary.html",
#         incomes=incomes,
#         total_income=total
#     )

 
@app.route("/income/list")
def manage_income():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    incomes = conn.execute(
        "SELECT * FROM income WHERE user_id = ? ORDER BY date DESC",
        (session["user_id"],)
    ).fetchall()
    conn.close()

    return render_template("manage_income.html", incomes=incomes)
from datetime import datetime

@app.route("/income/edit/<int:id>", methods=["GET", "POST"])
def edit_income(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    income = conn.execute(
        "SELECT * FROM income WHERE id = ? AND user_id = ?",
        (id, session["user_id"])
    ).fetchone()

    if not income:
        conn.close()
        return redirect(url_for("manage_income"))

    if request.method == "POST":
        source = request.form["source"]
        amount = float(request.form["amount"])
        date = request.form["date"]        # YYYY-MM-DD
        description = request.form.get("description")

        conn.execute("""
            UPDATE income
            SET source=?, amount=?, date=?, description=?
            WHERE id=? AND user_id=?
        """, (source, amount, date, description, id, session["user_id"]))
        conn.commit()
        conn.close()

        flash("Income updated successfully", "success")
        return redirect(url_for("manage_income"))

    conn.close()
    return render_template("edit_income.html", income=income)



# @app.route("/income/edit/<int:id>", methods=["GET", "POST"])
# def edit_income(id):
#     if "user_id" not in session:
#         return redirect(url_for("login"))

#     conn = get_db()
#     income = conn.execute(
#         "SELECT * FROM income WHERE id = ? AND user_id = ?",
#         (id, session["user_id"])
#     ).fetchone()

#     if not income:
#         conn.close()
#         return redirect(url_for("manage_income"))

#     if request.method == "POST":
#         source = request.form["source"]
#         amount = float(request.form["amount"])
#         date = request.form["date"]   # YYYY-MM-DD
#         description = request.form.get("description")

#         conn.execute("""
#             UPDATE income
#             SET source=?, amount=?, date=?, description=?
#             WHERE id=? AND user_id=?
#         """, (source, amount, date, description, id, session["user_id"]))
#         conn.commit()
#         conn.close()

#         return redirect(url_for("manage_income"))

#     # 🔥 CONVERT DATE FOR INPUT TYPE=DATE
#     formatted_income = dict(income)
#     formatted_income["date"] = datetime.strptime(
#         income["date"], "%d - %m - %Y"
#     ).strftime("%Y-%m-%d")

#     conn.close()
#     return render_template("edit_income.html", income=formatted_income)

@app.route("/income/delete-list")
def delete_income_list():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    incomes = conn.execute(
        "SELECT * FROM income WHERE user_id = ? ORDER BY date DESC",
        (session["user_id"],)
    ).fetchall()
    conn.close()

    return render_template("delete_income.html", incomes=incomes)


@app.route("/income/delete/<int:id>")
def delete_income(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    conn.execute(
        "DELETE FROM income WHERE id = ? AND user_id = ?",
        (id, session["user_id"])
    )
    conn.commit()
    conn.close()
    flash("Income deleted successfully", "danger")
    return redirect(url_for("delete_income_list"))


@app.route("/add-income", methods=["GET", "POST"])
def add_income():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        income_source = request.form.get("income_source")
        other_income = request.form.get("other_income_source")
        amount_raw = request.form.get("amount")
        date = request.form.get("date")
        description = request.form.get("description")

        if not income_source:
            flash("Please select income source")
            return redirect(url_for("add_income"))

        if income_source == "Other" and not other_income:
            flash("Please enter other income source")
            return redirect(url_for("add_income"))

        if not date:
            flash("Please select a date")
            return redirect(url_for("add_income"))

        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError
        except:
            flash("Please enter a valid income amount")
            return redirect(url_for("add_income"))

        final_source = (
            other_income.strip()
            if income_source == "Other"
            else income_source
        )

        conn = get_db()
        conn.execute("""
            INSERT INTO income (user_id, source, amount, date, description)
            VALUES (?, ?, ?, ?, ?)
        """, (session["user_id"], final_source, amount, date, description))
        conn.commit()
        conn.close()

        flash("Income added successfully!")
        return redirect(url_for("income_summary"))

    return render_template("add_income.html")



if __name__ == "__main__":
    app.run(debug=True)
print(app.url_map)