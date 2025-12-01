from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
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
    return "<h1>Flask alap rendszer működik</h1>"

# ADATBÁZIS LÉTREHOZÁS

# Ez akkor fut le, amikor indul a program
with app.app_context():
    db.create_all()

# APP FUTTATÁSA

if __name__ == "__main__":
    app.run(debug=True)
