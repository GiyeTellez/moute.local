from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import os
import json
import sqlite3
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "clave-secreta-moute-2026"

# -----------------------------
# Directorio base y rutas
# -----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "moute.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# -----------------------------
# Conexión a la base de datos
# -----------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# -----------------------------
# Inicializar base de datos (crear tablas si no existen)
# -----------------------------
def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # Tabla de administradores
    c.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Insertar admin por defecto si no existe
    c.execute("SELECT COUNT(*) FROM admins WHERE username = 'admin'")
    if c.fetchone()[0] == 0:
        default_password = "admin123"
        password_hash = generate_password_hash(default_password)
        c.execute("""
            INSERT INTO admins (username, password_hash, email) 
            VALUES (?, ?, ?)
        """, ("admin", password_hash, "admin@moute.com"))
        print(f"✅ Usuario admin creado con contraseña: {default_password}")
        print("⚠️  ¡Cambia la contraseña por defecto en el panel de administración!")
    
    conn.commit()
    conn.close()

# -----------------------------
# Decorador para requerir login de admin
# -----------------------------
def admin_required(f):
    def wrap(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash("Debes iniciar sesión como administrador para acceder a esta página.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

# -----------------------------
# Ejecutar inicialización al iniciar la app
# -----------------------------
with app.app_context():
    init_db()

# ============================
# LOGIN Y LOGOUT (ACTUALIZADO)
# ============================
@app.route("/login", methods=["GET", "POST"])
def login():
    # Si ya hay sesión activa, redirigir a eventos
    if session.get('logged_in'):
        return redirect(url_for('events'))
    
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        # Verificar si es admin
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, username, password_hash FROM admins WHERE username = ?", (username,))
        admin = c.fetchone()
        conn.close()
        
        if admin and check_password_hash(admin["password_hash"], password):
            # Login como administrador
            session['logged_in'] = True
            session['admin_logged_in'] = True
            session['admin_id'] = admin["id"]
            session['admin_username'] = admin["username"]
            session['username'] = admin["username"]
            flash("¡Inicio de sesión como administrador exitoso!", "success")
            return redirect(url_for('events'))
        else:
            # Login como usuario normal (solo visual)
            if username.strip():
                session['logged_in'] = True
                session['admin_logged_in'] = False
                session['username'] = username.strip()
                flash(f"¡Bienvenido, {username.strip()}!", "success")
                return redirect(url_for('events'))
            else:
                flash("Por favor, introduce un nombre de usuario.", "warning")
                return redirect(url_for('login'))
    
    return render_template("login.html", title="Iniciar Sesión")

@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada correctamente.", "info")
    return redirect(url_for('events'))

# ============================
# CAMBIAR CONTRASEÑA
# ============================
@app.route("/admin/change-password", methods=["GET", "POST"])
@admin_required
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")
        
        if not current_password or not new_password or not confirm_password:
            flash("Todos los campos son obligatorios.", "warning")
            return redirect(url_for('change_password'))
        
        if new_password != confirm_password:
            flash("Las nuevas contraseñas no coinciden.", "danger")
            return redirect(url_for('change_password'))
        
        if len(new_password) < 6:
            flash("La nueva contraseña debe tener al menos 6 caracteres.", "warning")
            return redirect(url_for('change_password'))
        
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT password_hash FROM admins WHERE id = ?", (session['admin_id'],))
        admin = c.fetchone()
        
        if not check_password_hash(admin["password_hash"], current_password):
            conn.close()
            flash("La contraseña actual es incorrecta.", "danger")
            return redirect(url_for('change_password'))
        
        new_password_hash = generate_password_hash(new_password)
        c.execute("UPDATE admins SET password_hash = ? WHERE id = ?", (new_password_hash, session['admin_id']))
        conn.commit()
        conn.close()
        
        flash("¡Contraseña cambiada exitosamente!", "success")
        return redirect(url_for('admin_panel'))
    
    return render_template("change_password.html", title="Cambiar Contraseña")

# ============================
# PANEL DE ADMINISTRACIÓN (CORREGIDO)
# ============================
@app.route("/admin")
@admin_required
def admin_panel():
    conn = get_db()
    c = conn.cursor()
    
    # Estadísticas generales
    c.execute("SELECT COUNT(*) FROM events")
    total_events = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM events WHERE data_inici >= date('now')")
    upcoming_events = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM events WHERE data_inici < date('now')")
    past_events = c.fetchone()[0]
    
    # Eventos por año
    c.execute("""
        SELECT strftime('%Y', data_inici) as year, COUNT(*) as count
        FROM events
        WHERE data_inici IS NOT NULL
        GROUP BY year
        ORDER BY year DESC
        LIMIT 10
    """)
    events_by_year = []
    for row in c.fetchall():
        events_by_year.append({"year": row["year"], "count": row["count"]})
    
    # Eventos por comarca/municipio (usando la columna que existe)
    c.execute("""
        SELECT 
            CASE 
                WHEN comarca_i_municipi LIKE '%barcelona%' THEN 'Barcelona'
                WHEN comarca_i_municipi LIKE '%girona%' THEN 'Girona'
                WHEN comarca_i_municipi LIKE '%lleida%' THEN 'Lleida'
                WHEN comarca_i_municipi LIKE '%tarragona%' THEN 'Tarragona'
                ELSE 'Otras'
            END as region,
            COUNT(*) as count
        FROM events
        WHERE comarca_i_municipi IS NOT NULL
        GROUP BY region
        ORDER BY count DESC
    """)
    events_by_region = []
    for row in c.fetchall():
        events_by_region.append({"region": row["region"], "count": row["count"]})
    
    # Categorías de eventos
    c.execute("""
        SELECT 
            CASE 
                WHEN tags_categories LIKE '%teatre%' THEN 'Teatro'
                WHEN tags_categories LIKE '%musica%' THEN 'Música'
                WHEN tags_categories LIKE '%exposicio%' OR tags_categories LIKE '%exposiciones%' THEN 'Exposiciones'
                WHEN tags_categories LIKE '%dansa%' THEN 'Danza'
                WHEN tags_categories LIKE '%cinema%' THEN 'Cine'
                WHEN tags_categories LIKE '%llibres%' OR tags_categories LIKE '%literatura%' THEN 'Literatura'
                WHEN tags_categories LIKE '%gastronomia%' THEN 'Gastronomía'
                ELSE 'Otros'
            END as category,
            COUNT(*) as count
        FROM events
        WHERE tags_categories IS NOT NULL
        GROUP BY category
        ORDER BY count DESC
        LIMIT 8
    """)
    events_by_category = []
    for row in c.fetchall():
        events_by_category.append({"category": row["category"], "count": row["count"]})
    
    # Eventos gratuitos vs pagos
    c.execute("""
        SELECT 
            CASE 
                WHEN entrades LIKE '%gratuit%' OR entrades LIKE '%gratis%' OR entrades LIKE '%gratuïta%' THEN 'Gratuitos'
                ELSE 'De pago'
            END as type,
            COUNT(*) as count
        FROM events
        GROUP BY type
    """)
    events_by_price = []
    for row in c.fetchall():
        events_by_price.append({"type": row["type"], "count": row["count"]})
    
    # Últimos 5 eventos añadidos
    c.execute("""
        SELECT id, denominacio, data_inici, created_at
        FROM events
        ORDER BY created_at DESC
        LIMIT 5
    """)
    recent_events = []
    for row in c.fetchall():
        recent_events.append({
            "id": row["id"], 
            "denominacio": row["denominacio"], 
            "data_inici": row["data_inici"], 
            "created_at": row["created_at"]
        })
    
    conn.close()
    
    stats = {
        "total_events": total_events,
        "upcoming_events": upcoming_events,
        "past_events": past_events,
        "events_by_year": events_by_year,
        "events_by_region": events_by_region,
        "events_by_category": events_by_category,
        "events_by_price": events_by_price,
        "recent_events": recent_events
    }
    
    return render_template("admin.html", title="Panel de Administración", stats=stats)

# ============================
# LISTAR EVENTOS
# ============================
@app.route("/")
@app.route("/events")
def events():
    return render_template("events.html", title="Eventos")

# ============================
# CALENDARIO DE EVENTOS
# ============================
@app.route("/calendar")
def calendar():
    return render_template("calendar.html", title="Calendario de Eventos")

# --- API para obtener eventos por mes ---
@app.route("/api/events-by-month")
def api_events_by_month():
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    
    if not year or not month:
        from datetime import datetime
        now = datetime.now()
        year = now.year
        month = now.month
    
    conn = get_db()
    c = conn.cursor()
    
    # Obtener primer y último día del mes
    import calendar as cal
    last_day = cal.monthrange(year, month)[1]
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year}-{month:02d}-{last_day}"
    
    c.execute("""
        SELECT id, denominacio, data_inici, data_fi, imatges
        FROM events
        WHERE data_inici BETWEEN ? AND ?
        ORDER BY data_inici
    """, (start_date, end_date))
    
    events = []
    for r in c.fetchall():
        events.append({
            "id": r["id"],
            "denominacio": r["denominacio"],
            "data_inici": r["data_inici"],
            "data_fi": r["data_fi"],
            "imatges": r["imatges"],
            "day": int(r["data_inici"].split("T")[0].split("-")[2]) if r["data_inici"] else None
        })
    
    conn.close()
    
    return jsonify({
        "year": year,
        "month": month,
        "events": events
    })

# ============================
# PÁGINA DE DETALLE DE EVENTO
# ============================
@app.route("/event/<event_id>")
def event_detail(event_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM events WHERE id = ?", (event_id,))
    event = c.fetchone()
    conn.close()
    
    if event is None:
        flash("Evento no encontrado", "danger")
        return redirect(url_for('events'))
    
    event_dict = dict(event)
    return render_template("event_detail.html", event=event_dict)

# ============================
# PÁGINA DE ACTUALIZACIÓN (protegida)
# ============================
@app.route("/update")
@admin_required
def update_events_page():
    return render_template("update_events.html", title="Actualizar BD")

# ============================
# PROCESAR JSON SUBIDO
# ============================
@app.route("/update_db", methods=["POST"])
@admin_required
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
    except Exception as e:
        flash(f"Archivo JSON inválido: {str(e)}", "danger")
        os.remove(path)
        return redirect(url_for("update_events_page"))
    finally:
        if os.path.exists(path):
            os.remove(path)

    conn = get_db()
    c = conn.cursor()
    nuevos = 0

    for item in data:
        id_event = item.get(":id")
        c.execute("SELECT COUNT(*) FROM events WHERE id = ?", (id_event,))
        if c.fetchone()[0] > 0:
            continue

        imatges_raw = item.get("imatges", "").strip()
        imatges = ""
        if imatges_raw:
            first_image = imatges_raw.split(",")[0].strip()
            if first_image.startswith("/"):
                imatges = "https://agenda.cultura.gencat.cat" + first_image
            elif first_image.startswith("http"):
                imatges = first_image

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
    return redirect(url_for("admin_panel"))

# --- API PAGINADA CON FILTROS ---
@app.route("/api/events")
def api_events():
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    offset = (page - 1) * per_page
    
    # Parámetros de filtrado
    query = request.args.get("q", "").strip().lower()
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    price_filter = request.args.get("price", "")
    category_filter = request.args.get("category", "")
    
    conn = get_db()
    c = conn.cursor()
    
    # Construir consulta base
    base_query = """
        SELECT id, denominacio, descripcio, imatges, data_inici, data_fi,
               horari, comarca_i_municipi, espai, entrades, url, tags_categories
        FROM events
    """
    
    conditions = []
    params = []
    
    # Filtro de búsqueda general
    if query:
        conditions.append("(LOWER(denominacio) LIKE ? OR LOWER(descripcio) LIKE ? OR LOWER(comarca_i_municipi) LIKE ? OR LOWER(espai) LIKE ?)")
        params.extend([f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"])
    
    # Filtro por fecha desde
    if date_from:
        conditions.append("data_inici >= ?")
        params.append(date_from)
    
    # Filtro por fecha hasta
    if date_to:
        conditions.append("data_inici <= ?")
        params.append(date_to)
    
    # Filtro por precio
    if price_filter:
        if price_filter == "free":
            conditions.append("(entrades LIKE '%gratuit%' OR entrades LIKE '%gratis%' OR entrades LIKE '%gratuïta%')")
        elif price_filter == "paid":
            conditions.append("NOT (entrades LIKE '%gratuit%' OR entrades LIKE '%gratis%' OR entrades LIKE '%gratuïta%')")
    
    # Filtro por categoría
    if category_filter:
        if category_filter == "teatre":
            conditions.append("tags_categories LIKE '%teatre%'")
        elif category_filter == "musica":
            conditions.append("tags_categories LIKE '%musica%'")
        elif category_filter == "exposicions":
            conditions.append("(tags_categories LIKE '%exposicio%' OR tags_categories LIKE '%exposiciones%')")
        elif category_filter == "dansa":
            conditions.append("tags_categories LIKE '%dansa%'")
        elif category_filter == "cinema":
            conditions.append("tags_categories LIKE '%cinema%'")
        elif category_filter == "literatura":
            conditions.append("(tags_categories LIKE '%llibres%' OR tags_categories LIKE '%literatura%')")
        elif category_filter == "gastronomia":
            conditions.append("tags_categories LIKE '%gastronomia%'")
    
    # Construir consulta final
    if conditions:
        where_clause = " WHERE " + " AND ".join(conditions)
        count_query = "SELECT COUNT(*) FROM events" + where_clause
        final_query = base_query + where_clause + " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([per_page, offset])
    else:
        count_query = "SELECT COUNT(*) FROM events"
        final_query = base_query + " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params = [per_page, offset]
    
    # Ejecutar consulta
    c.execute(final_query, params)
    rows = c.fetchall()
    
    # Contar total para paginación
    c.execute(count_query, params[:-2] if conditions else [])
    total_count = c.fetchone()[0]
    
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
    return jsonify({"events": events, "total": total_count})

# --- API DE BÚSQUEDA (SIMPLIFICADA) ---
@app.route("/api/search")
def api_search():
    query = request.args.get("q", "").strip().lower()
    if not query:
        return jsonify({"events": []})
    
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT id, denominacio, descripcio, imatges, data_inici, data_fi,
               horari, comarca_i_municipi, espai, entrades, url
        FROM events
        WHERE LOWER(denominacio) LIKE ? 
           OR LOWER(descripcio) LIKE ?
           OR LOWER(comarca_i_municipi) LIKE ?
           OR LOWER(espai) LIKE ?
        ORDER BY created_at DESC
        LIMIT 100
    """, (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"))
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

# --- API PARA OBTENER OPCIONES DE FILTRO ---
@app.route("/api/filters")
def api_filters():
    conn = get_db()
    c = conn.cursor()
    
    # Categorías disponibles
    c.execute("""
        SELECT DISTINCT 
            CASE 
                WHEN tags_categories LIKE '%teatre%' THEN 'teatre'
                WHEN tags_categories LIKE '%musica%' THEN 'musica'
                WHEN tags_categories LIKE '%exposicio%' OR tags_categories LIKE '%exposiciones%' THEN 'exposicions'
                WHEN tags_categories LIKE '%dansa%' THEN 'dansa'
                WHEN tags_categories LIKE '%cinema%' THEN 'cinema'
                WHEN tags_categories LIKE '%llibres%' OR tags_categories LIKE '%literatura%' THEN 'literatura'
                WHEN tags_categories LIKE '%gastronomia%' THEN 'gastronomia'
                ELSE 'altres'
            END as category
        FROM events
        WHERE tags_categories IS NOT NULL
        AND tags_categories != ''
    """)
    categories = [row["category"] for row in c.fetchall() if row["category"] != 'altres']
    
    conn.close()
    
    return jsonify({
        "categories": sorted(set(categories)),
        "price_options": ["free", "paid"]
    })

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