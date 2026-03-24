print("Flask imported successfully")

from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import uuid
import random
import time
import os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from collections import defaultdict

from datetime import datetime

def ui_to_db_date(date_str):
    return datetime.strptime(date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
def ui_to_db_date(date_str):
    from datetime import datetime

    try:
        # If already in YYYY-MM-DD format → return directly
        if "-" in date_str:
            return date_str

        # If in DD/MM/YYYY → convert
        return datetime.strptime(date_str, "%d/%m/%Y").strftime("%Y-%m-%d")

    except:
        return date_str
app = Flask(__name__)
app.secret_key = "finance_secret_key"

DATABASE = "instance/database.db"


# ================= DATABASE =================
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        profile_pic TEXT
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS income (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        source TEXT,
        amount REAL,
        date TEXT,
        description TEXT
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        category TEXT,
        date TEXT,
        note TEXT
    )
    """)

    # 🔥 GOALS TABLE
    conn.execute("""
    CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        target_amount REAL,
        saved_amount REAL DEFAULT 0,
        target_date TEXT,
        priority TEXT,
        achieved INTEGER DEFAULT 0
    )
    """)

    conn.commit()
    conn.close()


init_db()

def add_role_column():
    conn = get_db()
    try:
        conn.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
        conn.commit()
    except:
        pass
    conn.close()

add_role_column()

def admin_required(f):
    def wrapper(*args, **kwargs):

        # 🔐 Check login first
        if "user_id" not in session:
            return redirect("/login")

        # 🔍 Get user role
        conn = get_db()
        user = conn.execute(
            "SELECT role FROM users WHERE id=?",
            (session["user_id"],)
        ).fetchone()
        conn.close()

        # 🚫 Block non-admin
        if user["role"] != "admin":
            return "Access Denied", 403

        return f(*args, **kwargs)

    wrapper.__name__ = f.__name__
    return wrapper

#-----------ADMIN USER------------------
@app.route("/admin")
@admin_required
def admin_dashboard():

    conn = get_db()

    users = conn.execute(
        "SELECT id, name, email, role FROM users"
    ).fetchall()

    total_income = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM income"
    ).fetchone()[0]

    total_expense = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM expenses"
    ).fetchone()[0]

    total_goals = conn.execute(
        "SELECT COUNT(*) FROM goals"
    ).fetchone()[0]

    # 🔥 REQUIRED FOR PIE CHART
    admin_count = conn.execute(
        "SELECT COUNT(*) FROM users WHERE role='admin'"
    ).fetchone()[0]

    conn.close()

    return render_template(
        "admin.html",
        users=users,
        total_income=total_income,
        total_expense=total_expense,
        total_goals=total_goals,
        admin_count=admin_count
    )
    
#=============ADD USER================

@app.route("/add_user", methods=["POST"])
@admin_required
def add_user():

    name = request.form.get("name")
    email = request.form.get("email")
    password = request.form.get("password")

    if not name or not email or not password:
        flash("All fields are required", "danger")
        return redirect("/admin")

    conn = get_db()

    hashed_password = generate_password_hash(password)

    try:
        conn.execute("""
            INSERT INTO users (name, email, password, role)
            VALUES (?, ?, ?, ?)
        """, (name, email, hashed_password, "user"))

        conn.commit()
        flash("User added successfully", "success")

    except sqlite3.IntegrityError:
        flash("Email already exists", "danger")

    conn.close()

    return redirect("/admin")    

# ================= TOGGLE ADMIN =================
@app.route("/toggle-admin/<int:user_id>")
@admin_required
def toggle_admin(user_id):

    # ❌ prevent self edit
    if user_id == session["user_id"]:
        flash("You cannot change your own role!", "warning")
        return redirect("/admin")

    conn = get_db()

    user = conn.execute(
        "SELECT role FROM users WHERE id=?",
        (user_id,)
    ).fetchone()

    if not user:
        conn.close()
        return redirect("/admin")

    new_role = "admin" if user["role"] != "admin" else "user"

    conn.execute(
        "UPDATE users SET role=? WHERE id=?",
        (new_role, user_id)
    )

    conn.commit()
    conn.close()

    flash(f"Role updated to {new_role}", "success")

    return redirect("/admin")

#=====================DELETE USER==============
@app.route("/delete_user/<int:user_id>")
@admin_required
def delete_user(user_id):

    # ❌ prevent self delete
    if user_id == session["user_id"]:
        flash("You cannot delete yourself!", "danger")
        return redirect("/admin")

    conn = get_db()

    # delete related data
    conn.execute("DELETE FROM income WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM expenses WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM goals WHERE user_id=?", (user_id,))

    conn.execute("DELETE FROM users WHERE id=?", (user_id,))

    conn.commit()
    conn.close()

    flash("User deleted successfully", "success")

    return redirect("/admin")

# ================= GLOBAL USER (🔥 BEST FIX) =================
@app.context_processor
def inject_user():
    if "user_id" in session:
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE id=?",
            (session["user_id"],)
        ).fetchone()
        conn.close()
        return dict(user=user)
    return dict(user=None)

def upsert_salary(user_id, amount, date, description=None):
    conn = get_db()

    existing = conn.execute("""
        SELECT id FROM income
        WHERE user_id = ?
        AND source = 'Salary'
        AND strftime('%Y-%m', date) = strftime('%Y-%m', ?)
    """, (user_id, date)).fetchone()

    if existing:
        conn.execute("""
            UPDATE income
            SET amount=?, date=?, description=?
            WHERE id=?
        """, (amount, date, description, existing["id"]))
    else:
        conn.execute("""
            INSERT INTO income (user_id, source, amount, date, description)
            VALUES (?, 'Salary', ?, ?, ?)
        """, (user_id, amount, date, description))

    conn.commit()
    conn.close()


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

def add_category_column():
    conn = get_db()
    try:
        conn.execute("ALTER TABLE expenses ADD COLUMN category TEXT")
        conn.commit()
    except:
        pass  # column already exists
    conn.close()

add_category_column()

# ================= MONTHLY SAVINGS CALCULATION =================
def get_monthly_savings(user_id):
    conn = get_db()

    rows = conn.execute("""
        SELECT
            d.month AS month,
            COALESCE(SUM(i.amount), 0) - COALESCE(SUM(e.amount), 0) AS savings
        FROM (
            SELECT strftime('%Y-%m', date) AS month FROM income WHERE user_id = ?
            UNION
            SELECT strftime('%Y-%m', date) AS month FROM expenses WHERE user_id = ?
        ) d
        LEFT JOIN income i
            ON strftime('%Y-%m', i.date) = d.month AND i.user_id = ?
        LEFT JOIN expenses e
            ON strftime('%Y-%m', e.date) = d.month AND e.user_id = ?
        GROUP BY d.month
        ORDER BY d.month
    """, (user_id, user_id, user_id, user_id)).fetchall()

    conn.close()

    labels = []
    values = []

    for r in rows:
        labels.append(r["month"])
        values.append(float(r["savings"]))

    return labels, values
 

def get_monthly_financials(user_id):
    conn = get_db()

    rows = conn.execute("""
        SELECT month,
               SUM(income)  AS income,
               SUM(expense) AS expense
        FROM (
            SELECT strftime('%Y-%m', date) AS month,
                   SUM(amount) AS income,
                   0 AS expense
            FROM income
            WHERE user_id = ?
            GROUP BY month

            UNION ALL

            SELECT strftime('%Y-%m', date) AS month,
                   0 AS income,
                   SUM(amount) AS expense
            FROM expenses
            WHERE user_id = ?
            GROUP BY month
        )
        GROUP BY month
        ORDER BY month
    """, (user_id, user_id)).fetchall()

    conn.close()

    result = []
    for r in rows:
        income = float(r["income"] or 0)
        expense = float(r["expense"] or 0)
        result.append({
            "month": r["month"],
            "income": income,
            "expense": expense,
            "savings": income - expense
        })

    return result

#===============PROFILE===============
@app.route("/profile")
def profile():
    # ✅ 1. LOGIN VALIDATION
    if "user_id" not in session:
        flash("Please login first", "warning")
        return redirect(url_for("login"))

    conn = get_db()

    # ✅ 2. FETCH USER SAFELY
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    conn.close()

    # ✅ 3. USER EXISTENCE CHECK
    if not user:
        session.clear()
        flash("User not found. Please login again.", "danger")
        return redirect(url_for("login"))

    # ✅ 4. OPTIONAL PROFILE PIC FALLBACK
    profile_pic = user["profile_pic"] if user["profile_pic"] else "default.png"

    # ✅ 5. RENDER PROFILE PAGE (NOT DASHBOARD ❌)
    return render_template(
        "edit_profile.html",
        user=user,
        profile_pic=profile_pic
    )

# ================= DATE FILTER (🔥 ADD HERE) =================
@app.template_filter("pretty_date")
def pretty_date(value):
    from datetime import datetime
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d-%m-%Y")
    except:
        return value

# ---------------- LOGIN ----------------

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

@app.route("/reset_password", methods=["GET", "POST"])
def reset_password_page():

    if "user_id" not in session:
        flash("Please login first")
        return redirect(url_for("login"))

    if request.method == "POST":
        new_password = request.form.get("password")
        confirm_password = request.form.get("confirm")

        # ✅ VALIDATIONS
        if not new_password or not confirm_password:
            flash("All fields are required")
            return redirect(url_for("reset_password_page"))

        if len(new_password) < 6:
            flash("Password must be at least 6 characters")
            return redirect(url_for("reset_password_page"))

        if new_password != confirm_password:
            flash("Passwords do not match")
            return redirect(url_for("reset_password_page"))

        # ✅ UPDATE PASSWORD
        conn = get_db()

        hashed_password = generate_password_hash(new_password)

        conn.execute(
            "UPDATE users SET password=? WHERE id=?",
            (hashed_password, session["user_id"])
        )

        conn.commit()
        conn.close()

        flash("Password reset successfully!")
        return redirect(url_for("dashboard"))

    return render_template("reset_password.html")

# ---------------- EDIT PROFILE ----------------
UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/edit_profile", methods=["GET", "POST"])
def edit_profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")

        profile_pic = user["profile_pic"]

        if "profile_pic" in request.files:
            file = request.files["profile_pic"]
            if file and file.filename:
                filename = secure_filename(file.filename)
                file.save(os.path.join("static/uploads", filename))
                profile_pic = filename

        conn.execute("""
            UPDATE users
            SET name = ?, email = ?, profile_pic = ?
            WHERE id = ?
        """, (name, email, profile_pic, session["user_id"]))

        conn.commit()
        conn.close()

        flash("Profile updated successfully", "success")
        return redirect(url_for("profile"))

    conn.close()
    return render_template("edit_profile.html", user=user)


# ---------------- LOGOUT ----------------
@app.route("/logout", methods=["GET", "POST"])
def logout():
    if request.method == "POST":
        session.clear()
        return redirect(url_for("login"))

    return render_template("logout.html")

#------------SEND EMAIL-------------
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



def login_required(f):
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    user_id = session["user_id"]

    # TOTALS
    total_income = conn.execute(
        "SELECT SUM(amount) FROM income WHERE user_id=?",
        (user_id,)
    ).fetchone()[0] or 0

    total_expense = conn.execute(
        "SELECT SUM(amount) FROM expenses WHERE user_id=?",
        (user_id,)
    ).fetchone()[0] or 0

    total_savings = total_income - total_expense

    # MONTHLY DATA
    monthly = conn.execute("""
        SELECT strftime('%m', date) as month,
        SUM(CASE WHEN type='income' THEN amount ELSE 0 END) as income,
        SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) as expense
        FROM (
            SELECT amount, date, 'income' as type FROM income WHERE user_id=?
            UNION ALL
            SELECT amount, date, 'expense' as type FROM expenses WHERE user_id=?
        )
        GROUP BY month
        ORDER BY month
    """, (user_id, user_id)).fetchall()

    labels = [m["month"] for m in monthly]
    income_data = [m["income"] or 0 for m in monthly]
    expense_data = [m["expense"] or 0 for m in monthly]

    # CATEGORY BREAKDOWN (🔥 UPDATED)
    breakdown = conn.execute("""
        SELECT category, SUM(amount) as total
        FROM expenses
        WHERE user_id=?
        GROUP BY category
        ORDER BY total DESC
    """, (user_id,)).fetchall()

    data = [(b["category"], b["total"] or 0) for b in breakdown]

    top5 = data[:5]
    others_total = sum([x[1] for x in data[5:]])

    categories = [x[0] for x in top5]
    category_values = [x[1] for x in top5]

    if others_total > 0:
        categories.append("Others")
        category_values.append(others_total)

    # RECENT
    recent_transactions = conn.execute("""
        SELECT amount, category, date
        FROM expenses
        WHERE user_id=?
        ORDER BY date DESC LIMIT 5
    """, (user_id,)).fetchall()

    # GOALS
    goals = conn.execute(
    "SELECT * FROM goals WHERE user_id=? ORDER BY id DESC LIMIT 3",
       (user_id,)
    ).fetchall()
    # HEALTH SCORE
    health_score = int((total_savings / total_income) * 100) if total_income else 0

    conn.close()

    return render_template(
        "dashboard.html",
        total_income=round(total_income, 2),
        total_expense=round(total_expense, 2),
        total_savings=round(total_savings, 2),
        health_score=health_score,
        labels=labels,
        income_data=income_data,
        expense_data=expense_data,
        categories=categories,
        category_values=category_values,
        recent_transactions=recent_transactions,
        goals=goals
    )


# ================= INCOME =================

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
        "SELECT * FROM income WHERE id=? AND user_id=?",
        (id, session["user_id"])
    ).fetchone()

    if not income:
        conn.close()
        return redirect(url_for("manage_income"))

    if request.method == "POST":
        source = request.form.get("source")
        amount = float(request.form.get("amount"))

        raw_date = request.form.get("date")

        # ✅ FIX DATE HANDLING
        try:
            if raw_date and "-" in raw_date:
                date = raw_date   # already YYYY-MM-DD
            else:
                date = ui_to_db_date(raw_date)
        except:
            flash("Invalid date format")
            return redirect(url_for("edit_income", id=id))

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

# ------------------------ ADD INCOME ----------------------
@app.route("/add-income", methods=["GET", "POST"])
def add_income():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        income_source = request.form.get("income_source")
        other_income = request.form.get("other_income_source")
        amount_raw = request.form.get("amount")
        raw_date = request.form.get("date")
        description = request.form.get("description")

        # ✅ DATE FIX
        try:
            if raw_date and "-" in raw_date:
                date = raw_date
            else:
                date = ui_to_db_date(raw_date)
        except:
            flash("Invalid date format")
            return redirect(url_for("add_income"))

        # ✅ AMOUNT FIX
        try:
            amount = float(amount_raw)
        except:
            flash("Invalid amount")
            return redirect(url_for("add_income"))

        # ✅ SOURCE FIX
        final_source = (
            other_income.strip()
            if income_source == "Other" and other_income
            else income_source
        )

        conn = get_db()
        conn.execute("""
            INSERT INTO income (user_id, source, amount, date, description)
            VALUES (?, ?, ?, ?, ?)
        """, (session["user_id"], final_source, amount, date, description))

        conn.commit()
        conn.close()

        flash("Income added successfully")
        return redirect(url_for("income_summary"))

    return render_template("add_income.html")


#-------------format inr for expenses---------
def format_inr(amount):
    amount = int(amount)
    s = str(amount)

    if len(s) <= 3:
        return s

    last3 = s[-3:]
    rest = s[:-3]

    parts = []
    while len(rest) > 2:
        parts.insert(0, rest[-2:])
        rest = rest[:-2]

    if rest:
        parts.insert(0, rest)

    return ",".join(parts) + "," + last3

@app.route("/expense-management")
def expense_management():
    if "user_id" not in session:
        return redirect(url_for("login"))

    category = request.args.get("category")
    custom_category = request.args.get("custom_category")

    from_raw = request.args.get("from_date")
    to_raw = request.args.get("to_date")

    # ✅ normalize
    from_date = ui_to_db_date(from_raw) if from_raw else None
    to_date = ui_to_db_date(to_raw) if to_raw else None

    query = "SELECT * FROM expenses WHERE user_id=?"
    params = [session["user_id"]]

    if category:
        if category == "Other" and custom_category:
            query += " AND category=?"
            params.append(custom_category.strip())
        else:
            query += " AND category=?"
            params.append(category)

    if from_date:
        query += " AND date >= ?"
        params.append(from_date)

    if to_date:
        query += " AND date <= ?"
        params.append(to_date)

    query += " ORDER BY date DESC"

    conn = get_db()
    expenses = conn.execute(query, params).fetchall()

    total = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM (" + query + ") AS x",
        params
    ).fetchone()[0]

    conn.close()

    return render_template(
        "expense_management.html",
        expenses=expenses,
        total=total
    )
@app.route('/add-expense', methods=['GET', 'POST'])
def add_expense():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == 'POST':
        category = request.form['category']
        custom_category = request.form.get('custom_category')
        raw_date = request.form.get('date')  # DD/MM/YYYY

        try:
            date = ui_to_db_date(raw_date)   # ✅ FIX
        except:
            flash("Use date format DD/MM/YYYY")
            return redirect(url_for("add_expense"))

        final_category = (
            custom_category.strip()
            if category == "Other" and custom_category
            else category
        )

        conn = get_db()
        conn.execute("""
            INSERT INTO expenses (user_id, amount, category, date, note)
            VALUES (?, ?, ?, ?, ?)
        """, (
            session['user_id'],
            request.form['amount'],
            final_category,
            date,
            request.form['note']
        ))
        conn.commit()
        conn.close()

        flash("Expense added successfully")
        return redirect(url_for("expense_management"))

    return render_template('add_expense.html')


@app.route('/delete-expense/<int:id>')
def delete_expense(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    conn.execute(
        "DELETE FROM expenses WHERE id = ? AND user_id = ?",
        (id, session["user_id"])
    )
    conn.commit()
    conn.close()
    flash("Expense deleted successfully", "danger")
    return redirect(url_for("expense_management"))

#-----------------------------SAVINGS-----------------
@app.route("/savings")
def savings():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor()

    # TOTAL INCOME (ALL TIME)
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM income
        WHERE user_id = ?
    """, (session["user_id"],))
    total_income = cursor.fetchone()[0]

    # TOTAL EXPENSE (ALL TIME)
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE user_id = ?
    """, (session["user_id"],))
    total_expense = cursor.fetchone()[0]

    # SAVINGS
    total_savings = total_income - total_expense

    conn.close()

    return render_template(
        "savings.html",
        income=total_income,
        expense=total_expense,
        savings=total_savings
    )


def get_savings_summary(user_id, range_type):
    conn = get_db()

    if range_type == "month":
        date_filter = "date >= date('now','start of month')"
    elif range_type == "6months":
        date_filter = "date >= date('now','-6 months')"
    else:  # year
        date_filter = "date >= date('now','start of year')"

    # TOTALS
    income = conn.execute(
        f"SELECT COALESCE(SUM(amount),0) FROM income WHERE user_id=? AND {date_filter}",
        (user_id,)
    ).fetchone()[0]

    expense = conn.execute(
        f"SELECT COALESCE(SUM(amount),0) FROM expenses WHERE user_id=? AND {date_filter}",
        (user_id,)
    ).fetchone()[0]

    # MONTHLY BREAKUP FOR CHART
    rows = conn.execute(f"""
        SELECT month,
               SUM(income)  AS income,
               SUM(expense) AS expense
        FROM (
            SELECT strftime('%Y-%m', date) AS month,
                   SUM(amount) AS income,
                   0 AS expense
            FROM income
            WHERE user_id=? AND {date_filter}
            GROUP BY month

            UNION ALL

            SELECT strftime('%Y-%m', date) AS month,
                   0 AS income,
                   SUM(amount) AS expense
            FROM expenses
            WHERE user_id=? AND {date_filter}
            GROUP BY month
        )
        GROUP BY month
        ORDER BY month
    """, (user_id, user_id)).fetchall()

    conn.close()

    labels = []
    incomes = []
    expenses = []
    savings = []

    for r in rows:
        labels.append(r["month"])
        incomes.append(float(r["income"]))
        expenses.append(float(r["expense"]))
        savings.append(float(r["income"] - r["expense"]))

    return {
        "income": income,
        "expense": expense,
        "savings": income - expense,
        "labels": labels,
        "incomes": incomes,
        "expenses": expenses,
        "savings_list": savings
    }
    
@app.route("/api/savings/<range_type>")
def api_savings(range_type):
    if "user_id" not in session:
        return {"error": "unauthorized"}, 401

    user_id = session["user_id"]
    conn = get_db()

    if range_type == "month":
        date_filter = "strftime('%Y-%m', date) = strftime('%Y-%m', 'now')"

    elif range_type == "6months":
        date_filter = "date >= date('now','-6 months')"

    elif range_type == "year":
        # ✅ SHOW ALL DATA (KEY FIX)
        date_filter = "1=1"

    else:
        return {"error": "invalid range"}, 400

    rows = conn.execute(f"""
        SELECT strftime('%Y-%m', date) AS month,
               SUM(income) AS income,
               SUM(expense) AS expense
        FROM (
            SELECT date, amount AS income, 0 AS expense
            FROM income
            WHERE user_id=? AND {date_filter}

            UNION ALL

            SELECT date, 0 AS income, amount AS expense
            FROM expenses
            WHERE user_id=? AND {date_filter}
        )
        GROUP BY month
        ORDER BY month
    """, (user_id, user_id)).fetchall()

    conn.close()

    labels, incomes, expenses, savings_list = [], [], [], []
    total_income = 0
    total_expense = 0

    for r in rows:
        inc = float(r["income"] or 0)
        exp = float(r["expense"] or 0)

        labels.append(r["month"])
        incomes.append(inc)
        expenses.append(exp)
        savings_list.append(inc - exp)

        total_income += inc
        total_expense += exp

    return {
        "labels": labels,
        "incomes": incomes,
        "expenses": expenses,
        "savings_list": savings_list,
        "income": total_income,
        "expense": total_expense,
        "savings": total_income - total_expense
    }
    


# ================= FINANCIAL ANALYTICS =================
@app.route("/financial-analytics")
def financial_analytics():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    # USER
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    # MONTHLY INCOME
    income_rows = conn.execute("""
        SELECT strftime('%Y-%m', date) AS month, SUM(amount) AS total
        FROM income
        WHERE user_id = ?
        GROUP BY month
        ORDER BY month
    """, (session["user_id"],)).fetchall()

    # MONTHLY EXPENSE
    expense_rows = conn.execute("""
        SELECT strftime('%Y-%m', date) AS month, SUM(amount) AS total
        FROM expenses
        WHERE user_id = ?
        GROUP BY month
        ORDER BY month
    """, (session["user_id"],)).fetchall()

    income_dict = {r["month"]: float(r["total"]) for r in income_rows}
    expense_dict = {r["month"]: float(r["total"]) for r in expense_rows}

    months = sorted(set(income_dict) | set(expense_dict))
    income_values = [income_dict.get(m, 0) for m in months]
    expense_values = [expense_dict.get(m, 0) for m in months]

    # EXPENSE BREAKDOWN
    breakdown_rows = conn.execute("""
        SELECT category, SUM(amount) AS total
        FROM expenses
        WHERE user_id = ?
        GROUP BY category
    """, (session["user_id"],)).fetchall()

    categories = [r["category"] for r in breakdown_rows]
    category_amounts = [float(r["total"]) for r in breakdown_rows]

    # SAVINGS
    savings_months = months
    savings_values = [
        income_dict.get(m, 0) - expense_dict.get(m, 0)
        for m in months
    ]

    conn.close()

    return render_template(
        "financial_analytics.html",
        user=user,
        months=months,
        income_values=income_values,
        expense_values=expense_values,
        categories=categories,
        category_amounts=category_amounts,
        savings_months=savings_months,
        savings_values=savings_values
    )


# ================= GOALS =================
@app.route('/goals', methods=['GET', 'POST'])
def goals():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    # CREATE GOAL
    if request.method == "POST":
        conn.execute("""
    INSERT INTO goals (user_id, name, target_amount, saved_amount, target_date, priority, achieved)
    VALUES (?, ?, ?, 0, ?, ?, 0)
""", (
    session["user_id"],
    request.form.get("goal_name") or "Unnamed Goal",
    request.form["target_amount"],
    request.form["target_date"],
    request.form["priority"]
))
        conn.commit()

    # FETCH USER
    user = conn.execute(
        "SELECT * FROM users WHERE id=?",
        (session["user_id"],)
    ).fetchone()

    # FETCH GOALS
    goals = conn.execute(
        "SELECT * FROM goals WHERE user_id=? ORDER BY id DESC",
        (session["user_id"],)
    ).fetchall()

    conn.close()

    return render_template("goals.html", goals=goals, user=user)


# ================= ADD MONEY =================
@app.route("/goals/add/<int:goal_id>")
def add_money_goal(goal_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    goal = conn.execute(
        "SELECT * FROM goals WHERE id=? AND user_id=?",
        (goal_id, session["user_id"])
    ).fetchone()

    if goal:
        saved = goal["saved_amount"]
        target = goal["target_amount"]

        # 🚫 Stop if already achieved
        if saved >= target:
            conn.close()
            return redirect("/goals")

        new_amount = saved + 1000

        # 🔥 Cap at target
        if new_amount >= target:
            new_amount = target
            achieved = 1
        else:
            achieved = 0

        conn.execute(
            "UPDATE goals SET saved_amount=?, achieved=? WHERE id=?",
            (new_amount, achieved, goal_id)
        )

        conn.commit()

    conn.close()
    return redirect("/goals")


# ================= EDIT GOAL =================
@app.route("/goals/edit/<int:goal_id>", methods=["POST"])
def edit_goal(goal_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    conn.execute("""
        UPDATE goals
        SET name=?, target_amount=?, target_date=?, priority=?
        WHERE id=? AND user_id=?
    """, (
        request.form["goal_name"],
        request.form["target_amount"],
        request.form["target_date"],
        request.form["priority"],
        goal_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return redirect("/goals")


# ================= DELETE GOAL =================
@app.route("/goals/delete/<int:goal_id>")
def delete_goal(goal_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    conn.execute(
        "DELETE FROM goals WHERE id=? AND user_id=?",
        (goal_id, session["user_id"])
    )

    conn.commit()
    conn.close()

    return redirect("/goals")

# ================= SPENDING INSIGHTS =================
@app.route("/spending_insights")
def spending_insights():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    expenses = conn.execute(
        "SELECT amount, category, date FROM expenses WHERE user_id=?",
        (session["user_id"],)
    ).fetchall()

    conn.close()

    # ===== INIT =====
    months_map = defaultdict(lambda: {"needs":0, "wants":0})

    total_needs = 0
    total_wants = 0

    # ===== KEYWORDS FOR SMART CLASSIFICATION =====
    needs_keywords = [
        "rent", "food", "groceries", "bill",
        "electricity", "water", "medicine",
        "fees", "school", "college", "transport"
    ]

    # ===== PROCESS =====
    for e in expenses:
        amount = float(e["amount"])
        category = (e["category"] or "").lower()
        date = e["date"]

        # FIX DATE CRASH SAFELY
        try:
            month = datetime.strptime(date, "%Y-%m-%d").strftime("%b %Y")
        except:
            continue

        # ===== SMART CLASSIFICATION =====
        if any(k in category for k in needs_keywords):
            months_map[month]["needs"] += amount
            total_needs += amount
        else:
            months_map[month]["wants"] += amount
            total_wants += amount

    # ===== SORT MONTHS PROPERLY =====
    months = sorted(
        months_map.keys(),
        key=lambda x: datetime.strptime(x, "%b %Y")
    )

    needs_values = [months_map[m]["needs"] for m in months]
    wants_values = [months_map[m]["wants"] for m in months]

    # ===== HEALTH SCORE =====
    total = total_needs + total_wants
    health_score = 100 - int((total_wants / total) * 100) if total > 0 else 100

    # ===== INSIGHTS =====
    monthly_insights = {}
    leaderboard = []

    for m in months:
        needs = months_map[m]["needs"]
        wants = months_map[m]["wants"]

        total_m = needs + wants
        wants_pct = int((wants / total_m) * 100) if total_m > 0 else 0
        score = 100 - wants_pct

        # Insight logic
        if wants_pct > 60:
            insight = "⚠️ High unnecessary spending detected"
        elif wants_pct > 40:
            insight = "👍 Moderate spending, can improve"
        else:
            insight = "🔥 Excellent financial discipline"

        monthly_insights[m] = insight

        # Badge logic
        if score > 80:
            badge = "🔥 Excellent"
        elif score > 60:
            badge = "👍 Good"
        else:
            badge = "⚠️ Spender Alert"

        leaderboard.append({
            "month": m,
            "wants_pct": wants_pct,
            "score": score,
            "badge": badge
        })

    # ===== OVERALL INSIGHT =====
    if health_score > 80:
        overall_insight = "🔥 Excellent financial discipline!"
    elif health_score > 60:
        overall_insight = "👍 You're doing okay, but can improve."
    else:
        overall_insight = "⚠️ High unnecessary spending detected."

    return render_template(
        "spending_insights.html",
        months=months,
        needs_values=needs_values,
        wants_values=wants_values,
        total_needs=round(total_needs, 2),
        total_wants=round(total_wants, 2),
        health_score=health_score,
        monthly_insights=monthly_insights,
        leaderboard=leaderboard,
        overall_insight=overall_insight
    )

# ================== INVESTMENT DETAIL (FULL DATA) ==================

@app.route('/investment/<term>/<name>')
def investment_detail(term, name):

    if "user_id" not in session:
        return redirect("/login")

    data = {

        # ================= SHORT TERM =================
        "short": {

            "liquid_funds": {
                "title": "Liquid Mutual Funds",
                "return": "6.4% – 6.8%",
                "risk": "Very Low",
                "overview": "Safe short-term investment with instant liquidity.",
                "mechanism": "Invests in CDs, CPs, and T-Bills up to 91 days.",
                "performance": "Top funds delivering 6.4%–6.8% annually.",
                "extra": "Best for emergency funds with instant redemption.",
                "pros": [
                    "Instant redemption up to ₹50,000",
                    "Higher than savings account",
                    "Very stable returns"
                ],
                "cons": [
                    "Taxed at slab rate",
                    "Sensitive to RBI repo changes"
                ],
                "invest_link": "https://www.moneycontrol.com/mutual-funds/performance-tracker/returns/liquid-fund.html"
            },

            "high_yield_savings": {
                "title": "High-Yield Savings",
                "return": "6% – 7.25%",
                "risk": "Low",
                "overview": "Savings accounts offering higher interest.",
                "mechanism": "Bank savings accounts with dynamic rates.",
                "performance": "Top banks offer up to 7.25%.",
                "extra": "Safe parking with flexibility.",
                "pros": [
                    "Safe and regulated",
                    "Instant access",
                    "No lock-in"
                ],
                "cons": [
                    "Limited growth",
                    "Rate varies"
                ],
                "invest_link": "https://www.bankbazaar.com/savings-account/high-interest-savings-account.html"
            },

            "t_bills": {
                "title": "Treasury Bills",
                "return": "5.6% – 5.8%",
                "risk": "Zero Risk",
                "overview": "Government-backed short-term bonds.",
                "mechanism": "Issued by RBI at discount.",
                "performance": "Stable 5.6–5.8%.",
                "extra": "Safest option.",
                "pros": [
                    "Sovereign guarantee",
                    "Fixed returns",
                    "Very safe"
                ],
                "cons": [
                    "No periodic payouts",
                    "Less liquidity"
                ],
                "invest_link": "https://www.rbi.org.in/commonman/english/scripts/FAQs.aspx?Id=1456"
            }
        },

        # ================= MEDIUM =================
        "medium": {

            "equity_savings": {
                "title": "Equity Savings Funds",
                "return": "9% – 11%",
                "risk": "Moderate",
                "overview": "Mix of equity, arbitrage, debt.",
                "mechanism": "Balanced allocation strategy.",
                "performance": "10–12% CAGR.",
                "extra": "Tax-efficient.",
                "pros": ["Tax efficient", "Lower volatility", "Balanced growth"],
                "cons": ["Limited upside", "Manager dependent"],
                "invest_link": "https://www.moneycontrol.com/mutual-funds/performance-tracker/returns/equity-savings-fund.html"
            },

            "corporate_bonds": {
                "title": "Corporate Bonds",
                "return": "7.5% – 8.5%",
                "risk": "Low-Moderate",
                "overview": "Corporate debt investments.",
                "mechanism": "AAA-rated bonds.",
                "performance": "~8%.",
                "extra": "Better than FD.",
                "pros": ["Stable returns", "Better than FD", "Predictable"],
                "cons": ["Credit risk", "Taxed"],
                "invest_link": "https://www.moneycontrol.com/news/tags/corporate-bonds.html"
            },

            "gold_etf": {
                "title": "Gold ETF",
                "return": "Market Linked",
                "risk": "Moderate",
                "overview": "Tracks gold price.",
                "mechanism": "Backed by physical gold.",
                "performance": "Depends on gold.",
                "extra": "Inflation hedge.",
                "pros": ["Inflation hedge", "Easy trade", "Diversification"],
                "cons": ["Volatile", "No fixed returns"],
                "invest_link": "https://groww.in/gold-etf"
            }
        },

        # ================= LONG =================
        "long": {

            "mid_small_cap": {
                "title": "Mid Small Cap",
                "return": "15% – 22%",
                "risk": "High",
                "overview": "High-growth equity.",
                "mechanism": "Emerging companies.",
                "performance": "20%+",
                "extra": "Wealth creation.",
                "pros": ["High growth", "Compounding", "Wealth"],
                "cons": ["Volatility", "Risk"],
                "invest_link": "https://www.moneycontrol.com/mutual-funds/performance-tracker/returns/mid-cap-fund.html"
            },

            "ppf": {
                "title": "PPF",
                "return": "7% – 7.5%",
                "risk": "Zero Risk",
                "overview": "Govt savings scheme.",
                "mechanism": "15-year plan.",
                "performance": "~7.1%",
                "extra": "Tax-free.",
                "pros": ["Safe", "Tax-free", "Guaranteed"],
                "cons": ["Lock-in", "Low liquidity"],
                "invest_link": "https://www.nsiindia.gov.in/"
            },

            "nifty_next50": {
                "title": "Nifty Next 50",
                "return": "12% – 16%",
                "risk": "Moderate-High",
                "overview": "Tracks emerging large caps.",
                "mechanism": "Index fund.",
                "performance": "14–16%",
                "extra": "Future leaders.",
                "pros": ["Low cost", "Growth", "Diversified"],
                "cons": ["Market risk"],
                "invest_link": "https://groww.in/indices/nifty-next-50"
            }
        }
    }

    item = data.get(term, {}).get(name)

    if not item:
        return "Invalid investment", 404

    return render_template("investment_detail.html", item=item)

# ================== SMART ADVISOR (FULL COMPLETE VERSION) ==================
@app.route('/smart_advisor')
def smart_advisor():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    # 🔥 FETCH DATA
    incomes = conn.execute(
        "SELECT amount FROM income WHERE user_id=?",
        (session["user_id"],)
    ).fetchall()

    expenses = conn.execute(
        "SELECT amount, category, date FROM expenses WHERE user_id=?",
        (session["user_id"],)
    ).fetchall()

    conn.close()

    # ================== TOTALS ==================
    total_income = sum(i["amount"] for i in incomes)
    total_expense = sum(e["amount"] for e in expenses)
    savings = total_income - total_expense

    # ================== RATIOS ==================
    savings_rate = (savings / total_income) * 100 if total_income else 0
    expense_ratio = (total_expense / total_income) * 100 if total_income else 0

    # ================== HEALTH SCORE ==================
    risk_score = (savings_rate * 0.5) + ((100 - expense_ratio) * 0.5)
    health_score = int(risk_score)

    # ================== RISK PROFILE ==================
    if risk_score >= 70:
        risk_profile = "LOW RISK"
    elif risk_score >= 40:
        risk_profile = "MEDIUM RISK"
    else:
        risk_profile = "HIGH RISK"

    # ================== AI ADVICE ==================
    if risk_profile == "HIGH RISK":
        ai_advice = "⚠ Your savings are low. Focus on reducing unnecessary expenses and build an emergency fund."
    elif risk_profile == "MEDIUM RISK":
        ai_advice = "👍 You're on the right track. Consider diversifying into equity and long-term assets."
    else:
        ai_advice = "🔥 Excellent financial health! You can explore high-growth investments for wealth creation."

    # ================== ALERTS ==================
    alerts = []
    category_totals = defaultdict(float)

    for e in expenses:
        category = e["category"] or "Others"
        category_totals[category] += e["amount"]

    for cat, amt in category_totals.items():
        percent = (amt / total_income) * 100 if total_income else 0
        if percent > 20:
            alerts.append(f"{cat} spending is high ({round(percent,1)}%)")

    # ================== EXTRA SMART INSIGHTS ==================
    insights = []

    if savings_rate < 20:
        insights.append("Your savings rate is below 20%. Try increasing it.")

    if expense_ratio > 70:
        insights.append("You are spending more than 70% of your income.")

    if savings < 0:
        insights.append("You are spending more than you earn!")

    if not insights:
        insights.append("Your finances look stable. Keep it up!")

    # ================== MONTHLY TREND (OPTIONAL UI USE) ==================
    monthly_data = defaultdict(lambda: {"income": 0, "expense": 0})

    # (Optional — if you later add charts)
    # Not required for template but good for future extension

    # ================== FINAL RENDER ==================
    return render_template(
        "smart_advisor.html",
        savings_rate=round(savings_rate, 1),
        health_score=health_score,
        risk_profile=risk_profile,
        ai_advice=ai_advice,
        alerts=alerts,
        insights=insights
    )


@app.route("/home")
def home():
    return render_template("home.html")
#===================WELCOME PAGE==============
@app.route("/welcome")
def welcome():
    return render_template("welcome.html")

# ================= HOME PAGE =================
@app.route("/")
def index():
    return render_template("welcome.html")

print(app.url_map)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)