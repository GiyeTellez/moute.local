from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
import json
import sqlite3
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "clave-secreta-moute"

# -----------------------------
# Directorio base y rutas
# -----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "moute.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

# -----------------------------
# Conexión a la base de datos
# -----------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ============================
# LISTAR EVENTOS
# ============================
@app.route("/")
@app.route("/events")
def events():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, denominacio, descripcio, imatges FROM events ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    events_list = [
        {
            "id": r[0],
            "denominacio": r[1],
            "descripcio": r[2],
            "imatges": r[3]
        } for r in rows
    ]
    return render_template("events.html", title="Eventos", events=events_list)

# ============================
# PÁGINA DE ACTUALIZACIÓN
# ============================
@app.route("/update")
def update_events_page():
    return render_template("update_events.html", title="Actualizar BD")

# ============================
# PROCESAR JSON SUBIDO
# ============================
@app.route("/update_db", methods=["POST"])
def update_db_from_file():
    if "jsonfile" not in request.files:
        flash("No has subido ningún archivo.", "danger")
        return redirect(url_for("update_events_page"))

    file = request.files["jsonfile"]
    if file.filename == "":
        flash("Debes seleccionar un archivo.", "warning")
        return redirect(url_for("update_events_page"))

    filename = secure_filename(file.filename)
    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        flash("Archivo JSON inválido.", "danger")
        return redirect(url_for("update_events_page"))
    finally:
        os.remove(path)

    conn = get_db()
    c = conn.cursor()
    nuevos = 0

    for item in data:
        id_event = item.get(":id")
        # Comprobar si ya existe
        c.execute("SELECT COUNT(*) FROM events WHERE id = ?", (id_event,))
        if c.fetchone()[0] > 0:
            continue

        # Construir enlace a imagen
        imatges = ""
        links = item.get("enlla_os", "")
        if links:
            base_url = links.split(",")[0]
            if item.get("imatges", "").startswith("/"):
                imatges = base_url + item.get("imatges")

        # Insertar registro
        c.execute("""
            INSERT INTO events (
                id, version, created_at, updated_at, codi, data_fi, data_inici,
                denominacio, subtitol, descripcio, tags_ambits, tags_categories,
                entrades, horari, links, imatges, adreca, comarca_i_municipi,
                espai, latitud, longitud, telefon, url, imgapp, descripcio_html,
                municipi, comarca
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            id_event,
            item.get(":version", ""),
            item.get(":created_at", ""),
            item.get(":updated_at", ""),
            item.get("codi", ""),
            item.get("data_fi", ""),
            item.get("data_inici", ""),
            item.get("denominaci", ""),
            item.get("subt_tol", ""),
            item.get("descripcio", ""),
            item.get("tags_mbits", ""),
            item.get("tags_categor_es", ""),
            item.get("entrades", ""),
            item.get("horari", ""),
            item.get("enlla_os", ""),
            imatges,
            item.get("adre_a", ""),
            item.get("comarca_i_municipi", ""),
            item.get("espai", ""),
            item.get("latitud", ""),
            item.get("longitud", ""),
            item.get("tel_fon", ""),
            item.get("url", ""),
            item.get("imgapp", ""),
            item.get("descripcio_html", ""),
            item.get("municipi", ""),
            item.get("comarca", "")
        ))
        nuevos += 1

    conn.commit()
    conn.close()
    flash(f"{nuevos} nuevos eventos añadidos.", "success")
    return redirect(url_for("events"))

# --- API PAGINADA ---
@app.route("/api/events")
def api_events():
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))  # Ahora acepta per_page variable
    offset = (page - 1) * per_page

    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT id, denominacio, descripcio, imatges, data_inici, data_fi,
               horari, comarca_i_municipi, espai, entrades, url
        FROM events
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    """, (per_page, offset))
    rows = c.fetchall()
    conn.close()

    events = []
    for r in rows:
        events.append({
            "id": r["id"],
            "denominacio": r["denominacio"],
            "descripcio": r["descripcio"],
            "imatges": r["imatges"],
            "data_inici": r["data_inici"],
            "data_fi": r["data_fi"],
            "horari": r["horari"],
            "comarca_i_municipi": r["comarca_i_municipi"],
            "espai": r["espai"],
            "entrades": r["entrades"],
            "url": r["url"],
        })
    return jsonify({"events": events})

# ============================
# NUEVA RUTA: Favoritos
# ============================
@app.route("/favorites")
def favorites():
    return render_template("favorites.html", title="Mis Favoritos")

# ============================
# MAIN
# ============================
if __name__ == "__main__":
    app.run(debug=True)