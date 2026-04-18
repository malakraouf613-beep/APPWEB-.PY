from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime
import hashlib
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "thermo-secret-key-change-in-prod")

ADMINS = {
    "admin1@thermo.com": hashlib.sha256("Admin1Pass!".encode()).hexdigest(),
    "admin2@thermo.com": hashlib.sha256("Admin2Pass!".encode()).hexdigest(),
}

def init_db():
    db = sqlite3.connect("database.db")
    cursor = db.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pressions_sat (
        compose TEXT PRIMARY KEY,
        p_sat REAL
    )""")
    cursor.execute("INSERT OR REPLACE INTO pressions_sat VALUES ('Benzène', 101.3)")
    cursor.execute("INSERT OR REPLACE INTO pressions_sat VALUES ('Toluène', 40.0)")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        email TEXT,
        login_time TEXT,
        logout_time TEXT,
        duration_minutes REAL,
        password_reset INTEGER DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")
    db.commit()
    db.close()

init_db()

def get_db():
    return sqlite3.connect("database.db")

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        hashed = hash_pw(password)
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT id, email FROM users WHERE email=? AND password=?", (email, hashed))
        user = cursor.fetchone()
        if user:
            session["user_id"] = user[0]
            session["user_email"] = user[1]
            session["login_time"] = datetime.now().isoformat()
            cursor.execute("INSERT INTO user_sessions (user_id, email, login_time) VALUES (?, ?, ?)",
                           (user[0], user[1], session["login_time"]))
            db.commit()
            cursor.execute("SELECT last_insert_rowid()")
            session["session_db_id"] = cursor.fetchone()[0]
            db.close()
            return redirect(url_for("index"))
        else:
            db.close()
            flash("Email ou mot de passe incorrect.", "error")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        if password != confirm:
            flash("Les mots de passe ne correspondent pas.", "error")
            return render_template("register.html")
        if len(password) < 6:
            flash("Le mot de passe doit contenir au moins 6 caractères.", "error")
            return render_template("register.html")
        db = get_db()
        try:
            db.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, hash_pw(password)))
            db.commit()
            db.close()
            flash("Compte créé avec succès ! Connectez-vous.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            db.close()
            flash("Cet email est déjà utilisé.", "error")
    return render_template("register.html")

@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        old_pw = request.form.get("old_password", "")
        new_pw = request.form.get("new_password", "")
        confirm = request.form.get("confirm", "")
        if new_pw != confirm:
            flash("Les nouveaux mots de passe ne correspondent pas.", "error")
            return render_template("reset_password.html")
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT id FROM users WHERE id=? AND password=?",
                       (session["user_id"], hash_pw(old_pw)))
        if cursor.fetchone():
            cursor.execute("UPDATE users SET password=? WHERE id=?",
                           (hash_pw(new_pw), session["user_id"]))
            if "session_db_id" in session:
                cursor.execute("UPDATE user_sessions SET password_reset=1 WHERE id=?",
                               (session["session_db_id"],))
            db.commit()
            db.close()
            flash("Mot de passe modifié avec succès !", "success")
        else:
            db.close()
            flash("Ancien mot de passe incorrect.", "error")
    return render_template("reset_password.html")

@app.route("/logout")
def logout():
    if "session_db_id" in session and "login_time" in session:
        login_time = datetime.fromisoformat(session["login_time"])
        logout_time = datetime.now()
        duration = (logout_time - login_time).total_seconds() / 60.0
        db = get_db()
        db.execute("UPDATE user_sessions SET logout_time=?, duration_minutes=? WHERE id=?",
                   (logout_time.isoformat(), round(duration, 2), session["session_db_id"]))
        db.commit()
        db.close()
    session.clear()
    return redirect(url_for("login"))

@app.route("/", methods=["GET", "POST"])
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))
    y1 = y2 = None
    erreur = None
    if request.method == "POST":
        try:
            x1 = float(request.form["x1"])
            x2 = float(request.form["x2"])
            if round(x1 + x2, 2) != 1:
                erreur = "x1 + x2 doit être égal à 1"
            else:
                db = get_db()
                cursor = db.cursor()
                cursor.execute("SELECT p_sat FROM pressions_sat WHERE compose='Benzène'")
                p1 = cursor.fetchone()[0]
                cursor.execute("SELECT p_sat FROM pressions_sat WHERE compose='Toluène'")
                p2 = cursor.fetchone()[0]
                db.close()
                denom = (x1 * p1) + (x2 * p2)
                y1 = (x1 * p1) / denom
                y2 = (x2 * p2) / denom
        except:
            erreur = "Erreur dans les valeurs saisies"
    return render_template("index.html", y1=y1, y2=y2, erreur=erreur,
                           user_email=session.get("user_email"))

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if email in ADMINS and ADMINS[email] == hash_pw(password):
            session["admin"] = True
            session["admin_email"] = email
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Identifiants administrateur incorrects.", "error")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    session.pop("admin_email", None)
    return redirect(url_for("admin_login"))

@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, email, created_at FROM users ORDER BY created_at DESC")
    users = cursor.fetchall()
    cursor.execute("""
        SELECT us.id, us.email, us.login_time, us.logout_time,
               us.duration_minutes, us.password_reset
        FROM user_sessions us ORDER BY us.login_time DESC LIMIT 100
    """)
    sessions_data = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM user_sessions WHERE logout_time IS NOT NULL")
    total_sessions = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM user_sessions WHERE password_reset=1")
    total_resets = cursor.fetchone()[0]
    db.close()
    return render_template("admin_dashboard.html",
                           users=users, sessions_data=sessions_data,
                           total_users=total_users, total_sessions=total_sessions,
                           total_resets=total_resets,
                           admin_email=session.get("admin_email"))

if __name__ == "__main__":
    app.run(debug=True)
