print("Flask imported successfully")
from flask import jsonify
from flask import Flask, render_template, request, redirect, url_for, session, flash
import json
from flask import Flask, render_template, request, jsonify
import sqlite3
import uuid
import random
import time
import os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
goals = []
goal_id = 1
app = Flask(__name__)
app.secret_key = "finance_secret_key"
# -------- LOAD & SAVE --------
def load_goals():
    try:
        with open("goals.json", "r") as f:
            return json.load(f)
    except:
        return []

def save_goals(goals):
    with open("goals.json", "w") as f:
        json.dump(goals, f)
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
def ui_to_db_date(date_str):
    """
    Accepts:
    - DD/MM/YYYY
    - YYYY-MM-DD
    Returns:
    - YYYY-MM-DD (DB safe)
    """
    try:
        # Case 1: DD/MM/YYYY
        if "/" in date_str:
            return datetime.strptime(date_str, "%d/%m/%Y").strftime("%Y-%m-%d")

        # Case 2: YYYY-MM-DD (already DB format)
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")

    except ValueError:
        raise ValueError("Invalid date format")

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
     # ✅ EXPENSES TABLE (ADD THIS)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            note TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)


    conn.commit()
    conn.close()

init_db()
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

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template("dashboard.html")


@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template("profile.html")



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
        return redirect(url_for("dashboard"))

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

    monthly_income = get_monthly_income(session["user_id"])

    return render_template(
        "income_summary.html",
        incomes=incomes,
        total_income=total,
        monthly_income=monthly_income
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
        date = request.form["date"]   # ✅ FIXED
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

    return redirect(url_for("delete_income_list"))   # ✅ FIXED
 

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




@app.route("/add-income", methods=["GET", "POST"])
def add_income():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        income_source = request.form.get("income_source")
        other_income = request.form.get("other_income_source")
        amount_raw = request.form.get("amount")
        raw_date = request.form.get("date")  # DD/MM/YYYY
        description = request.form.get("description")

        try:
            date = ui_to_db_date(raw_date)   # ✅ FIX
        except:
            flash("Use date format DD/MM/YYYY")
            return redirect(url_for("add_income"))

        try:
            amount = float(amount_raw)
        except:
            flash("Invalid amount")
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

        flash("Income added successfully")
        return redirect(url_for("income_summary"))

    return render_template("add_income.html")
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
# ================= GOALS (FINAL VERSION) =================
import json
from flask import request, jsonify, render_template

# -------- LOAD & SAVE --------
def load_goals():
    try:
        with open("goals.json", "r") as f:
            return json.load(f)
    except:
        return []

def save_goals(goals):
    with open("goals.json", "w") as f:
        json.dump(goals, f)


# -------- GOALS PAGE --------
@app.route("/goals")
def goals_page():
    goals = load_goals()

    # ✅ SAFE CALCULATION (prevents Jinja error)
    total = sum(g.get("saved", 0) for g in goals)
    active = len(goals)

    return render_template("goals.html", goals=goals, total=total, active=active)


# -------- ADD GOAL --------
@app.route("/add_goal", methods=["POST"])
def add_goal():
    data = request.json
    goals = load_goals()

    # VALIDATION
    if not data.get("title") or not data.get("target"):
        return jsonify({"error": "Missing fields"})

    if float(data.get("target")) <= 0:
        return jsonify({"error": "Target must be greater than 0"})

    new_goal = {
        "id": len(goals) + 1,
        "title": data["title"],
        "target": float(data["target"]),
        "saved": 0,
        "priority": data.get("priority", "Medium"),
        "date": data.get("date")
    }

    goals.append(new_goal)
    save_goals(goals)

    # ✅ IMPORTANT RESPONSE
    return jsonify({
        "success": True,
        "goal": new_goal
    })

# -------- ADD MONEY --------
@app.route("/update_goal/<int:id>", methods=["POST"])
def update_goal(id):
    data = request.json
    amount = float(data.get("amount", 0))

    goals = load_goals()

    for g in goals:
        if g["id"] == id:

            # ❌ INVALID INPUT
            if amount <= 0:
                return jsonify({"error": "Invalid amount"})

            # ❌ OVERFLOW PREVENTION
            if g.get("saved", 0) + amount > g.get("target", 0):
                return jsonify({"error": "Amount exceeds target"})

            # ✅ UPDATE
            g["saved"] = g.get("saved", 0) + amount

    save_goals(goals)
    return jsonify({"success": True})


# -------- DELETE GOAL --------
@app.route("/delete_goal/<int:id>", methods=["POST"])
def delete_goal(id):
    goals = load_goals()

    goals = [g for g in goals if g["id"] != id]

    save_goals(goals)
    return jsonify({"success": True})


@app.route("/dashboard-data")
def dashboard_data():

    # ✅ AUTH CHECK FIRST
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db()

    # ✅ FIXED COLUMN NAME HERE
    user = conn.execute(
        "SELECT name, profile_pic FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    # ================= TOTALS =================
    income = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM income WHERE user_id = ?",
        (session["user_id"],)
    ).fetchone()[0]

    expenses = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = ?",
        (session["user_id"],)
    ).fetchone()[0]

    savings = income - expenses

    # ================= TRANSACTIONS =================
    transactions = conn.execute("""
        SELECT 'income' as type, amount, date, source as title FROM income
        WHERE user_id = ?
        
        UNION ALL
        
        SELECT 'expense' as type, amount, date, category as title FROM expenses
        WHERE user_id = ?
        
        ORDER BY date DESC
    """, (session["user_id"], session["user_id"])).fetchall()

    # ================= GOALS =================
    goals_data = load_goals()
    goals = []

    for g in goals_data:
        goals.append({
            "title": g.get("title"),
            "target_amount": g.get("target", 0),
            "saved_amount": g.get("saved", 0)
        })

    conn.close()

    # ================= RESPONSE =================
    return jsonify({
        "income": income,
        "expenses": expenses,
        "savings": savings,
        "transactions": [dict(row) for row in transactions],
        "goals": goals,

        # ✅ FIXED USER DATA
        "user_name": user["name"] if user else "User",
        "user_image": f"/static/uploads/{user['profile_pic']}" if user and user["profile_pic"] else "/static/images/default.png"
    })

if __name__ == "__main__":
    app.run(debug=True)
  
