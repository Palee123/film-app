from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask import render_template, redirect, url_for, request, flash, session
from flask_login import login_user, logout_user, login_required, current_user
import os
import requests

# APP ALAP BEÁLLÍTÁS

app = Flask(__name__, instance_relative_config=True)

# Betöltjük a secret key-t
secret_path = os.path.join(app.instance_path, "secret_key.txt")
with open(secret_path, "r") as f:
    app.config["SECRET_KEY"] = f.read().strip()

# TMDb API kulcs betöltése
tmdb_key_path = os.path.join(app.root_path, "tmdb_key.txt")
with open(tmdb_key_path, "r") as f:
    TMDB_API_KEY = f.read().strip()

# Globális lang változó elérhető a sablonokban
@app.context_processor
def inject_lang():
    return {"lang": session.get("lang", "hu")}

def get_tmdb_language():
    lang = session.get("lang", "hu")  # 'hu' az alap
    if lang == "en":
        return "en-US"
    return "hu-HU"


TMDB_BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"


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

class Rating(db.Model):
    __tablename__ = "ratings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    movie_id = db.Column(db.Integer, nullable=False)
    rating = db.Column(db.Integer, nullable=False)

    # Egyszer egy user csak egyszer értékelhet egy filmet
    __table_args__ = (db.UniqueConstraint("user_id", "movie_id"),)

class Favorite(db.Model):
    __tablename__ = "favorites"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    movie_id = db.Column(db.Integer, nullable=False)

    __table_args__ = (db.UniqueConstraint("user_id", "movie_id"),)


# Flask-Login user loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def get_popular_movies():
    url = f"{TMDB_BASE_URL}/movie/popular"
    params = {
        "api_key": TMDB_API_KEY,
        "language": get_tmdb_language(),
        "page": 1
    }
    response = requests.get(url, params=params).json()
    movies = response.get("results", [])
    print("POPULAR MOVIES COUNT:", len(movies))
    return movies


@app.route("/")
def index():
    movies = get_popular_movies()
    return render_template("index.html", movies=movies,image_base=IMAGE_BASE_URL)

@app.route("/set_language/<lang>")
def set_language(lang):
    if lang not in ["hu", "en"]:
        lang = "hu"
    session["lang"] = lang
    return redirect(request.referrer or url_for("index"))


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

# KERESŐ OLDAL

@app.route("/search")
def search():
    genres = get_genres()
    return render_template("search.html", genres=genres)

# KERESŐ OLDAL - EREDMÉNYEK

@app.route("/search/results")
def search_results():

    query = request.args.get("query")
    genre_id = request.args.get("genre")

    params = {
    "api_key": TMDB_API_KEY,
    "language": get_tmdb_language(),
    "query": query,
    }

    url = f"{TMDB_BASE_URL}/search/movie"
    response = requests.get(url, params=params).json()
    results = response.get("results", [])

    # Ha műfaj is ki van választva → szűrés
    if genre_id and genre_id != "0":
        genre_id = int(genre_id)
        results = [movie for movie in results if genre_id in movie.get("genre_ids", [])]

    return render_template("search_results.html",
                           results=results,
                           image_base=IMAGE_BASE_URL)

#film részletek

@app.route("/movie/<int:movie_id>")
def movie_details(movie_id):
    # Film adatok lekérése TMDb API-ból
    url = f"{TMDB_BASE_URL}/movie/{movie_id}"
    params = {"api_key": TMDB_API_KEY, "language": get_tmdb_language()}
    movie = requests.get(url, params=params).json()


    # Kép elérési út
    poster = IMAGE_BASE_URL + movie["poster_path"] if movie.get("poster_path") else None

    # Átlag értékelés saját DB-ből
    ratings = Rating.query.filter_by(movie_id=movie_id).all()
    avg_rating = None
    if ratings:
        avg_rating = sum(r.rating for r in ratings) / len(ratings)

    # Saját értékelés (ha van)
    user_rating = None
    if current_user.is_authenticated:
        r = Rating.query.filter_by(user_id=current_user.id, movie_id=movie_id).first()
        if r:
            user_rating = r.rating

    # Kedvenc-e?
    is_favorite = False
    if current_user.is_authenticated:
        fav = Favorite.query.filter_by(user_id=current_user.id, movie_id=movie_id).first()
        if fav:
            is_favorite = True

    return render_template("movie_details.html",
                           movie=movie,
                           poster=poster,
                           avg_rating=avg_rating,
                           user_rating=user_rating,
                           is_favorite=is_favorite)

@app.route("/favorites")
@login_required
def favorites():
    favorites = Favorite.query.filter_by(user_id=current_user.id).all()

    movies = []
    lang_code = get_tmdb_language()

    for fav in favorites:
        url = f"{TMDB_BASE_URL}/movie/{fav.movie_id}"
        params = {"api_key": TMDB_API_KEY, "language": lang_code}
        movie = requests.get(url, params=params).json()
        if movie and "id" in movie:
            movies.append(movie)
            
    print("MOVIES DEBUG:", movies)

    return render_template("favorites.html",
                           movies=movies,
                           image_base=IMAGE_BASE_URL)

@app.route("/remove_favorite/<int:movie_id>")
@login_required
def remove_favorite(movie_id):
    fav = Favorite.query.filter_by(user_id=current_user.id, movie_id=movie_id).first()
    if fav:
        db.session.delete(fav)
        db.session.commit()
        flash("Kedvencekből eltávolítva!", "info")
    else:
        flash("Ez a film nincs a kedvencek között!", "warning")


    return redirect(request.referrer or url_for("favorites"))


@app.route("/my_ratings")
@login_required
def my_ratings():
    ratings = Rating.query.filter_by(user_id=current_user.id).all()

    movie_data = []
    lang_code = get_tmdb_language()

    for r in ratings:
        url = f"{TMDB_BASE_URL}/movie/{r.movie_id}"
        params = {"api_key": TMDB_API_KEY, "language": lang_code}
        movie = requests.get(url, params=params).json()

        if movie and "id" in movie:
            movie_data.append({
                "movie": movie,
                "rating": r.rating
            })

    return render_template("my_ratings.html",
                           movie_data=movie_data,
                           image_base=IMAGE_BASE_URL)


#értékelés mentése

@app.route("/rate/<int:movie_id>", methods=["POST"])
@login_required
def rate_movie(movie_id):
    rating_value = int(request.form.get("rating"))

    existing = Rating.query.filter_by(user_id=current_user.id, movie_id=movie_id).first()

    if existing:
        existing.rating = rating_value
    else:
        new_rating = Rating(user_id=current_user.id, movie_id=movie_id, rating=rating_value)
        db.session.add(new_rating)

    db.session.commit()
    flash("Sikeresen értékelted a filmet!", "success")
    return redirect(url_for("movie_details", movie_id=movie_id))

#kedvenc hozzáadása

@app.route("/favorite/<int:movie_id>")
@login_required
def add_favorite(movie_id):
    fav = Favorite.query.filter_by(user_id=current_user.id, movie_id=movie_id).first()

    if not fav:
        new_fav = Favorite(user_id=current_user.id, movie_id=movie_id)
        db.session.add(new_fav)
        db.session.commit()
        flash("Hozzáadva a kedvencekhez!", "success")
    else:
        flash("Ez a film már a kedvencek között van!", "info")

    return redirect(url_for("movie_details", movie_id=movie_id))


# TMDB - műfajlista lekérése
def get_genres():
    lang_code = get_tmdb_language()
    url = f"{TMDB_BASE_URL}/genre/movie/list?api_key={TMDB_API_KEY}&language={lang_code}"
    response = requests.get(url).json()
    return response.get("genres", [])


# ADATBÁZIS LÉTREHOZÁS
# Ez akkor fut le, amikor indul a program
with app.app_context():
    db.create_all()


# APP FUTTATÁSA

if __name__ == "__main__":
    app.run(debug=True)
