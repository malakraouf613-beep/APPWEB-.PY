from flask import Flask, render_template, request
import sqlite3

app = Flask(__name__)

# 🔹 Initialisation base SQLite
def init_db():
    db = sqlite3.connect("database.db")
    cursor = db.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pressions_sat (
        compose TEXT PRIMARY KEY,
        p_sat REAL
    )
    """)

    cursor.execute("INSERT OR REPLACE INTO pressions_sat VALUES ('Benzène', 101.3)")
    cursor.execute("INSERT OR REPLACE INTO pressions_sat VALUES ('Toluène', 40.0)")

    db.commit()
    db.close()

init_db()

# 🔹 Connexion DB
def get_db():
    return sqlite3.connect("database.db")

@app.route("/", methods=["GET", "POST"])
def index():
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
            erreur = "Erreur dans les valeurs"

    return render_template("index.html", y1=y1, y2=y2, erreur=erreur)

if __name__ == "__main__":
    app.run(debug=True)