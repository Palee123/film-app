from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask import render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
import os

# APP ALAP BEÁLLÍTÁS

app = Flask(__name__, instance_relative_config=True)

# Betöltjük a secret key-t
secret_path = os.path.join(app.instance_path, "secret_key.txt")
with open(secret_path, "r") as f:
    app.config["SECRET_KEY"] = f.read().strip()

# SQLite adatbázis
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Login kezelő
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"  # akkor fogjuk használni, ha lesz login

# USER MODELL (User tábla)

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(300), nullable=False)

    # jelszó hash-elése
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    # jelszó ellenőrzése
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Flask-Login user loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# TESZT ÚTVONAL (Később törölhető)

@app.route("/")
def index():
    return render_template("base.html")

# REGISZTRÁCIÓ
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        # ellenőrzés, hogy nincs-e már ilyen felhasználó
        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()

        if existing_user:
            flash("Ez a felhasználónév vagy email már létezik!", "danger")
            return redirect(url_for("register"))

        # új user létrehozása
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        flash("Sikeres regisztráció! Jelentkezz be!", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

# BEJELENTKEZÉS

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username_or_email = request.form.get("username")
        password = request.form.get("password")

        # keresés username vagy email alapján
        user = User.query.filter(
            (User.username == username_or_email) | 
            (User.email == username_or_email)
        ).first()

        if user and user.check_password(password):
            login_user(user)
            flash("Sikeres bejelentkezés!", "success")
            return redirect(url_for("index"))
        else:
            flash("Hibás adatok!", "danger")

    return render_template("login.html")

# KIJELENTKEZÉS

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Sikeresen kijelentkeztél!", "info")
    return redirect(url_for("login"))

# ADATBÁZIS LÉTREHOZÁS
# Ez akkor fut le, amikor indul a program
with app.app_context():
    db.create_all()

# APP FUTTATÁSA

if __name__ == "__main__":
    app.run(debug=True)
