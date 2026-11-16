import os
import io
import sqlite3
import secrets
from functools import wraps
from datetime import datetime

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, abort
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

APP_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(APP_DIR, "database.db")
UPLOAD_DIR = os.path.join(APP_DIR, "uploads")
ALLOWED_EXTENSIONS = {"csv"}
MAX_CONTENT_LENGTH = 20 * 1024 * 1024

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR
os.makedirs(UPLOAD_DIR, exist_ok=True)

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS datasets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                filename TEXT NOT NULL,
                stored_name TEXT NOT NULL,
                uploaded_by INTEGER NOT NULL,
                uploaded_at TEXT NOT NULL,
                FOREIGN KEY(uploaded_by) REFERENCES users(id)
            )
        """)
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count == 0:
            conn.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, 'admin', ?)",
                ("admin", generate_password_hash("admin123"), datetime.now().strftime("%d/%m/%Y %H:%M"))
            )

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            abort(403)
        return fn(*args, **kwargs)
    return wrapper

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def get_dataset(dataset_id):
    with db() as conn:
        row = conn.execute("""
            SELECT d.*, u.username AS uploader
            FROM datasets d JOIN users u ON u.id = d.uploaded_by
            WHERE d.id = ?
        """, (dataset_id,)).fetchone()
    if not row:
        abort(404)
    path = os.path.join(UPLOAD_DIR, row["stored_name"])
    if not os.path.isfile(path):
        abort(404)
    return row, path

def read_dataset(path):
    # Tenta UTF-8 e, se necessário, a codificação comum em arquivos exportados no Windows.
    try:
        return pd.read_csv(path, sep=None, engine="python", encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(path, sep=None, engine="python", encoding="latin-1")

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with db() as conn:
            user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            return redirect(url_for("dashboard"))
        flash("Usuário ou senha incorretos.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    with db() as conn:
        datasets = conn.execute("""
            SELECT d.*, u.username AS uploader
            FROM datasets d JOIN users u ON u.id = d.uploaded_by
            ORDER BY d.id DESC
        """).fetchall()
    selected = request.args.get("dataset", type=int)
    if not selected and datasets:
        selected = datasets[0]["id"]
    analysis = None
    if selected:
        row, path = get_dataset(selected)
        try:
            df = read_dataset(path)
            numeric = df.select_dtypes(include="number")
            columns = list(df.columns)
            stats = []
            for col in numeric.columns:
                series = numeric[col].dropna()
                stats.append({
                    "name": str(col),
                    "mean": round(float(series.mean()), 2) if len(series) else 0,
                    "median": round(float(series.median()), 2) if len(series) else 0,
                    "min": round(float(series.min()), 2) if len(series) else 0,
                    "max": round(float(series.max()), 2) if len(series) else 0,
                    "std": round(float(series.std()), 2) if len(series) > 1 else 0,
                })
            analysis = {
                "dataset": row,
                "rows": int(len(df)),
                "cols": int(len(df.columns)),
                "missing": int(df.isna().sum().sum()),
                "numeric_count": int(len(numeric.columns)),
                "columns": columns,
                "stats": stats,
                "preview": df.head(8).fillna("").astype(str).to_dict(orient="records"),
            }
        except Exception as exc:
            flash(f"Não foi possível analisar o arquivo: {exc}", "danger")
    return render_template("dashboard.html", datasets=datasets, selected=selected, analysis=analysis)

@app.route("/upload", methods=["POST"])
@login_required
def upload():
    file = request.files.get("file")
    title = request.form.get("title", "").strip()
    if not file or not file.filename:
        flash("Selecione um arquivo CSV.", "warning")
        return redirect(url_for("dashboard"))
    if not allowed_file(file.filename):
        flash("Formato inválido. Envie somente arquivos .csv.", "danger")
        return redirect(url_for("dashboard"))
    original = secure_filename(file.filename)
    stored = f"{secrets.token_hex(12)}_{original}"
    path = os.path.join(UPLOAD_DIR, stored)
    file.save(path)
    try:
        df = read_dataset(path)
        if df.empty or len(df.columns) == 0:
            raise ValueError("O CSV está vazio.")
    except Exception as exc:
        os.remove(path)
        flash(f"CSV inválido: {exc}", "danger")
        return redirect(url_for("dashboard"))
    with db() as conn:
        cur = conn.execute("""
            INSERT INTO datasets (title, filename, stored_name, uploaded_by, uploaded_at)
            VALUES (?, ?, ?, ?, ?)
        """, (title or original, original, stored, session["user_id"], datetime.now().strftime("%d/%m/%Y %H:%M")))
        dataset_id = cur.lastrowid
    flash("Arquivo importado e analisado com sucesso.", "success")
    return redirect(url_for("dashboard", dataset=dataset_id))

@app.route("/dataset/<int:dataset_id>/chart/<chart_type>")
@login_required
def chart(dataset_id, chart_type):
    row, path = get_dataset(dataset_id)
    df = read_dataset(path)
    numeric = df.select_dtypes(include="number")
    if numeric.empty:
        abort(404)
    column = request.args.get("column")
    if column not in numeric.columns:
        column = numeric.columns[0]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    if chart_type == "hist":
        ax.hist(numeric[column].dropna(), bins=12, edgecolor="white")
        ax.set_title(f"Distribuição de {column}")
        ax.set_xlabel(str(column))
        ax.set_ylabel("Frequência")
    elif chart_type == "bar":
        numeric[column].dropna().head(20).plot(kind="bar", ax=ax)
        ax.set_title(f"Valores de {column} (primeiros 20 registros)")
        ax.set_xlabel("Registro")
        ax.set_ylabel(str(column))
    else:
        abort(404)
    fig.tight_layout()
    output = io.BytesIO()
    fig.savefig(output, format="png", dpi=110)
    plt.close(fig)
    output.seek(0)
    return send_file(output, mimetype="image/png")

@app.route("/admin/users")
@login_required
@admin_required
def users():
    with db() as conn:
        all_users = conn.execute("SELECT id, username, role, created_at FROM users ORDER BY id").fetchall()
    return render_template("users.html", users=all_users)

@app.route("/admin/users/create", methods=["POST"])
@login_required
@admin_required
def create_user():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    role = request.form.get("role", "user")
    if len(username) < 3 or len(password) < 6:
        flash("O usuário deve ter ao menos 3 caracteres e a senha ao menos 6.", "danger")
    elif role not in ("user", "admin"):
        flash("Perfil inválido.", "danger")
    else:
        try:
            with db() as conn:
                conn.execute(
                    "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                    (username, generate_password_hash(password), role, datetime.now().strftime("%d/%m/%Y %H:%M"))
                )
            flash("Usuário criado com sucesso.", "success")
        except sqlite3.IntegrityError:
            flash("Esse nome de usuário já existe.", "danger")
    return redirect(url_for("users"))

@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    if user_id == session["user_id"]:
        flash("Você não pode excluir sua própria conta.", "danger")
        return redirect(url_for("users"))
    with db() as conn:
        target = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not target:
            flash("Usuário não encontrado.", "danger")
        elif target["role"] == "admin":
            admins = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]
            if admins <= 1:
                flash("Não é possível excluir o último administrador.", "danger")
            else:
                conn.execute("DELETE FROM datasets WHERE uploaded_by = ?", (user_id,))
                conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
                flash("Administrador excluído.", "success")
        else:
            conn.execute("DELETE FROM datasets WHERE uploaded_by = ?", (user_id,))
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            flash("Usuário excluído.", "success")
    return redirect(url_for("users"))

@app.errorhandler(403)
def forbidden(_):
    return render_template("error.html", code=403, message="Você não tem permissão para acessar esta página."), 403

@app.errorhandler(404)
def not_found(_):
    return render_template("error.html", code=404, message="O conteúdo solicitado não foi encontrado."), 404

init_db()

if __name__ == "__main__":
    # Acesse por http://IP_DO_SERVIDOR:5000 nos computadores da mesma rede.
    app.run(host="0.0.0.0", port=5000, debug=False)
