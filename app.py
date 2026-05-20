# =============================================================================
# IMPORTS Y CONFIGURACIÓN INICIAL
# =============================================================================
# Importamos las herramientas necesarias de Flask para rutas, plantillas, peticiones, etc.
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
# Importamos módulos estándar de Python para manejo de archivos, JSON y base de datos
import os
import json
import sqlite3
# Importamos utilidades de Werkzeug para seguridad en nombres de archivo y hashing de contraseñas
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# Creamos la instancia principal de la aplicación Flask
app = Flask(__name__)
# Clave secreta para firmar sesiones y cookies (en producción debería ser más segura y no estar hardcodeada)
app.secret_key = "clave-secreta-moute-2026"

# =============================================================================
# CONFIGURACIÓN DE RUTAS Y BASE DE DATOS
# =============================================================================
# Calculamos la ruta absoluta del directorio donde está este archivo app.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Definimos la ruta completa al archivo de base de datos SQLite
DB_PATH = os.path.join(BASE_DIR, "moute.db")
# Definimos la carpeta donde se guardarán temporalmente los archivos JSON subidos
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
# Creamos la carpeta de uploads si no existe (exist_ok=True evita error si ya existe)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# =============================================================================
# FUNCIÓN PARA CONECTAR A LA BASE DE DATOS
# =============================================================================
def get_db():
    """
    Establece y devuelve una conexión a la base de datos SQLite.
    row_factory = sqlite3.Row permite acceder a las columnas por nombre (no solo por índice).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# =============================================================================
# INICIALIZACIÓN DE LA BASE DE DATOS (CREAR TABLAS SI NO EXISTEN)
# =============================================================================
def init_db():
    """
    Crea las tablas necesarias si no existen y configura un usuario admin por defecto.
    Se ejecuta automáticamente al iniciar la aplicación.
    """
    conn = get_db()  # Obtenemos conexión a la BD
    c = conn.cursor()  # Creamos un cursor para ejecutar consultas
    
    # --- CREAR TABLA DE ADMINISTRADORES ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # --- CREAR USUARIO ADMIN POR DEFECTO (si no existe) ---
    c.execute("SELECT COUNT(*) FROM admins WHERE username = 'admin'")
    if c.fetchone()[0] == 0:  # Si no hay ningún admin con username 'admin'
        default_password = "admin123"  # Contraseña por defecto (¡cambiar en producción!)
        # Hasheamos la contraseña para almacenarla de forma segura
        password_hash = generate_password_hash(default_password)
        # Insertamos el nuevo admin en la base de datos
        c.execute("""
            INSERT INTO admins (username, password_hash, email) 
            VALUES (?, ?, ?)
        """, ("admin", password_hash, "admin@moute.com"))
        # Mensajes de consola para confirmar la creación
        print(f" Usuario admin creado con contraseña: {default_password}")
        print("  ¡Cambia la contraseña por defecto en el panel de administración!")
    
    # Guardamos los cambios y cerramos la conexión
    conn.commit()
    conn.close()

# =============================================================================
# DECORADOR PARA PROTEGER RUTAS DE ADMINISTRADOR
# =============================================================================
def admin_required(f):
    """
    Decorador personalizado que verifica si el usuario tiene sesión de administrador activa.
    Si no la tiene, redirige al login con un mensaje de advertencia.
    """
    def wrap(*args, **kwargs):
        # Verificamos si la sesión tiene la flag 'admin_logged_in' activada
        if not session.get('admin_logged_in'):
            flash("Debes iniciar sesión como administrador para acceder a esta página.", "warning")
            return redirect(url_for('login'))  # Redirigimos al login si no está autorizado
        return f(*args, **kwargs)  # Si está autorizado, ejecutamos la función original
    wrap.__name__ = f.__name__  # Preservamos el nombre original de la función para debugging
    return wrap

# =============================================================================
# EJECUTAR INICIALIZACIÓN AL ARRANCAR LA APLICACIÓN
# =============================================================================
# Este bloque se ejecuta UNA VEZ cuando la app arranca, asegurando que la BD está lista
with app.app_context():
    init_db()

# =============================================================================
# RUTAS DE AUTENTICACIÓN: LOGIN Y LOGOUT
# =============================================================================
@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Maneja el inicio de sesión: permite acceso como admin (con contraseña) 
    o como usuario normal (solo nombre visual).
    """
    # Si ya hay una sesión activa, redirigimos directamente a la página de eventos
    if session.get('logged_in'):
        return redirect(url_for('events'))
    
    # Si el método es POST, significa que el usuario ha enviado el formulario de login
    if request.method == "POST":
        username = request.form.get("username")  # Obtenemos el username del formulario
        password = request.form.get("password")   # Obtenemos la contraseña del formulario
        
        # --- VERIFICAR SI ES ADMINISTRADOR ---
        conn = get_db()
        c = conn.cursor()
        # Buscamos el admin en la BD usando parámetros preparados (previene inyección SQL)
        c.execute("SELECT id, username, password_hash FROM admins WHERE username = ?", (username,))
        admin = c.fetchone()  # Obtenemos el resultado (None si no existe)
        conn.close()
        
        # Si existe el admin Y la contraseña coincide con el hash almacenado
        if admin and check_password_hash(admin["password_hash"], password):
            # --- LOGIN COMO ADMINISTRADOR ---
            session['logged_in'] = True           # Flag general de sesión activa
            session['admin_logged_in'] = True     # Flag específica de rol admin
            session['admin_id'] = admin["id"]     # Guardamos ID del admin en sesión
            session['admin_username'] = admin["username"]  # Guardamos username del admin
            session['username'] = admin["username"]        # Username para mostrar en UI
            flash("¡Inicio de sesión como administrador exitoso!", "success")
            return redirect(url_for('events'))  # Redirigimos a eventos
        else:
            # --- LOGIN COMO USUARIO NORMAL (solo visual, sin validación de contraseña) ---
            if username.strip():  # Si el username no está vacío
                session['logged_in'] = True           # Activamos sesión general
                session['admin_logged_in'] = False    # Marcamos que NO es admin
                session['username'] = username.strip() # Guardamos nombre para mostrar
                flash(f"¡Bienvenido, {username.strip()}!", "success")
                return redirect(url_for('events'))  # Redirigimos a eventos
            else:
                # Si el username está vacío, mostramos error y volvemos al login
                flash("Por favor, introduce un nombre de usuario.", "warning")
                return redirect(url_for('login'))
    
    # Si es GET (primera visita), renderizamos la plantilla de login
    return render_template("login.html", title="Iniciar Sesión")

@app.route("/logout")
def logout():
    """
    Cierra la sesión del usuario eliminando todos los datos de sesión.
    """
    session.clear()  # Borra toda la información de la sesión actual
    flash("Sesión cerrada correctamente.", "info")  # Mensaje de confirmación
    return redirect(url_for('events'))  # Redirige a la página principal

# =============================================================================
# RUTA: CAMBIAR CONTRASEÑA (SOLO ADMIN)
# =============================================================================
@app.route("/admin/change-password", methods=["GET", "POST"])
@admin_required  # Decorador: solo accesible si es admin
def change_password():
    """
    Permite al administrador cambiar su contraseña de forma segura.
    """
    if request.method == "POST":
        # Obtenemos los datos del formulario
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")
        
        # Validaciones básicas de campos
        if not current_password or not new_password or not confirm_password:
            flash("Todos los campos son obligatorios.", "warning")
            return redirect(url_for('change_password'))
        
        if new_password != confirm_password:
            flash("Las nuevas contraseñas no coinciden.", "danger")
            return redirect(url_for('change_password'))
        
        if len(new_password) < 6:
            flash("La nueva contraseña debe tener al menos 6 caracteres.", "warning")
            return redirect(url_for('change_password'))
        
        # --- VERIFICAR CONTRASEÑA ACTUAL ---
        conn = get_db()
        c = conn.cursor()
        # Obtenemos el hash almacenado del admin actual
        c.execute("SELECT password_hash FROM admins WHERE id = ?", (session['admin_id'],))
        admin = c.fetchone()
        
        # Comparamos la contraseña introducida con el hash almacenado
        if not check_password_hash(admin["password_hash"], current_password):
            conn.close()
            flash("La contraseña actual es incorrecta.", "danger")
            return redirect(url_for('change_password'))
        
        # --- ACTUALIZAR CONTRASEÑA ---
        new_password_hash = generate_password_hash(new_password)  # Hasheamos la nueva
        c.execute("UPDATE admins SET password_hash = ? WHERE id = ?", (new_password_hash, session['admin_id']))
        conn.commit()  # Guardamos cambios en BD
        conn.close()
        
        flash("¡Contraseña cambiada exitosamente!", "success")
        return redirect(url_for('admin_panel'))  # Redirigimos al panel de admin
    
    # Si es GET, mostramos el formulario de cambio de contraseña
    return render_template("change_password.html", title="Cambiar Contraseña")

# =============================================================================
# RUTA: PANEL DE ADMINISTRACIÓN (SOLO ADMIN)
# =============================================================================
@app.route("/admin")
@admin_required  # Decorador: solo accesible si es admin
def admin_panel():
    """
    Muestra estadísticas y métricas de la base de datos para el administrador.
    """
    conn = get_db()
    c = conn.cursor()
    
    # --- ESTADÍSTICAS GENERALES ---
    c.execute("SELECT COUNT(*) FROM events")  # Total de eventos
    total_events = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM events WHERE data_inici >= date('now')")  # Eventos futuros
    upcoming_events = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM events WHERE data_inici < date('now')")  # Eventos pasados
    past_events = c.fetchone()[0]
    
    # --- EVENTOS POR AÑO (últimos 10 años con eventos) ---
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
    
    # --- EVENTOS POR COMARCA (agrupación simplificada por provincia) ---
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
    
    # --- EVENTOS POR CATEGORÍA CULTURAL ---
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
    
    # --- EVENTOS GRATUITOS VS DE PAGO ---
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
    
    # --- ÚLTIMOS 5 EVENTOS AÑADIDOS ---
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
    
    conn.close()  # Cerramos conexión a BD
    
    # Empaquetamos todas las estadísticas en un diccionario para pasar a la plantilla
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

# =============================================================================
# RUTAS PÚBLICAS: LISTADO DE EVENTOS Y CALENDARIO
# =============================================================================
@app.route("/")
@app.route("/events")
def events():
    """
    Página principal: muestra el listado de eventos (events.html).
    Accesible tanto en '/' como en '/events'.
    """
    return render_template("events.html", title="Eventos")

@app.route("/calendar")
def calendar():
    """
    Página de calendario: muestra vista mensual interactiva (calendar.html).
    """
    return render_template("calendar.html", title="Calendario de Eventos")

# =============================================================================
# API: EVENTOS POR MES (PARA CALENDARIO)
# =============================================================================
@app.route("/api/events-by-month")
def api_events_by_month():
    """
    Endpoint AJAX: devuelve eventos de un mes específico en formato JSON.
    Usado por el calendario para cargar eventos dinámicamente.
    """
    # Obtenemos año y mes de los parámetros URL (?year=2026&month=4)
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    
    # Si no se proporcionan, usamos el mes y año actuales
    if not year or not month:
        from datetime import datetime
        now = datetime.now()
        year = now.year
        month = now.month
    
    conn = get_db()
    c = conn.cursor()
    
    # Calculamos primer y último día del mes para el filtro de fechas
    import calendar as cal
    last_day = cal.monthrange(year, month)[1]  # Ej: abril tiene 30 días
    start_date = f"{year}-{month:02d}-01"       # Ej: "2026-04-01"
    end_date = f"{year}-{month:02d}-{last_day}" # Ej: "2026-04-30"
    
    # Consultamos eventos que empiecen dentro de ese rango de fechas
    c.execute("""
        SELECT id, denominacio, data_inici, data_fi, imatges
        FROM events
        WHERE data_inici BETWEEN ? AND ?
        ORDER BY data_inici
    """, (start_date, end_date))
    
    # Procesamos resultados y extraemos el día del mes para el calendario
    events = []
    for r in c.fetchall():
        events.append({
            "id": r["id"],
            "denominacio": r["denominacio"],
            "data_inici": r["data_inici"],
            "data_fi": r["data_fi"],
            "imatges": r["imatges"],
            "day": int(r["data_inici"].split("T")[0].split("-")[2]) if r["data_inici"] else None  # Extrae día: "2026-04-15" → 15
        })
    
    conn.close()
    
    # Devolvemos respuesta JSON para el frontend
    return jsonify({
        "year": year,
        "month": month,
        "events": events
    })

# =============================================================================
# RUTA: DETALLE DE UN EVENTO
# =============================================================================
@app.route("/event/<event_id>")
def event_detail(event_id):
    """
    Muestra la página de detalle de un evento específico.
    <event_id> es un parámetro dinámico en la URL.
    """
    conn = get_db()
    c = conn.cursor()
    # Buscamos el evento por su ID único
    c.execute("SELECT * FROM events WHERE id = ?", (event_id,))
    event = c.fetchone()
    conn.close()
    
    # Si no se encuentra el evento, mostramos error y redirigimos
    if event is None:
        flash("Evento no encontrado", "danger")
        return redirect(url_for('events'))
    
    # Convertimos el resultado Row a diccionario para pasar a la plantilla
    event_dict = dict(event)
    return render_template("event_detail.html", event=event_dict)

# =============================================================================
# RUTA: PÁGINA DE ACTUALIZACIÓN DE BD (SOLO ADMIN)
# =============================================================================
@app.route("/update")
@admin_required
def update_events_page():
    """
    Muestra el formulario para subir archivos JSON y actualizar la BD.
    """
    return render_template("update_events.html", title="Actualizar BD")

# =============================================================================
# API: PROCESAR JSON SUBIDO (SOLO ADMIN)
# =============================================================================
@app.route("/update_db", methods=["POST"])
@admin_required
def update_db_from_file():
    """
    Procesa un archivo JSON subido por el admin e inserta nuevos eventos en la BD.
    Evita duplicados verificando el ID único de cada evento.
    """
    # Validar que se haya subido un archivo
    if "jsonfile" not in request.files:
        flash("No has subido ningún archivo.", "danger")
        return redirect(url_for("update_events_page"))

    file = request.files["jsonfile"]
    if file.filename == "":
        flash("Debes seleccionar un archivo.", "warning")
        return redirect(url_for("update_events_page"))

    # Guardar archivo temporalmente con nombre seguro
    filename = secure_filename(file.filename)
    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)

    try:
        # Intentar leer y parsear el JSON
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        # Si hay error al leer JSON, mostrar mensaje y limpiar archivo
        flash(f"Archivo JSON inválido: {str(e)}", "danger")
        os.remove(path)
        return redirect(url_for("update_events_page"))
    finally:
        # Siempre eliminar el archivo temporal después de procesarlo
        if os.path.exists(path):
            os.remove(path)

    conn = get_db()
    c = conn.cursor()
    nuevos = 0  # Contador de eventos insertados

    # Iterar sobre cada evento del JSON
    for item in data:
        id_event = item.get(":id")  # El ID único viene con prefijo ':' en el JSON original
        
        # Verificar si el evento ya existe en la BD (evitar duplicados)
        c.execute("SELECT COUNT(*) FROM events WHERE id = ?", (id_event,))
        if c.fetchone()[0] > 0:
            continue  # Si ya existe, saltamos a la siguiente iteración

        # Procesar imágenes: convertir URLs relativas a absolutas si es necesario
        imatges_raw = item.get("imatges", "").strip()
        imatges = ""
        if imatges_raw:
            first_image = imatges_raw.split(",")[0].strip()  # Tomamos solo la primera imagen si hay varias
            if first_image.startswith("/"):
                imatges = "https://agenda.cultura.gencat.cat" + first_image  # Completar URL relativa
            elif first_image.startswith("http"):
                imatges = first_image  # URL absoluta, usar tal cual

        # Insertar el nuevo evento en la BD con todos sus campos
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
            item.get("denominaci", ""),      # Nota: campo con posible error tipográfico en el JSON original
            item.get("subt_tol", ""),        # Nota: campo con posible error tipográfico en el JSON original
            item.get("descripcio", ""),
            item.get("tags_mbits", ""),      # Nota: campo con posible error tipográfico en el JSON original
            item.get("tags_categor_es", ""), # Nota: campo con posible error tipográfico en el JSON original
            item.get("entrades", ""),
            item.get("horari", ""),
            item.get("enlla_os", ""),        # Nota: campo con posible error tipográfico en el JSON original
            imatges,
            item.get("adre_a", ""),          # Nota: campo con posible error tipográfico en el JSON original
            item.get("comarca_i_municipi", ""),
            item.get("espai", ""),
            item.get("latitud", ""),
            item.get("longitud", ""),
            item.get("tel_fon", ""),         # Nota: campo con posible error tipográfico en el JSON original
            item.get("url", ""),
            item.get("imgapp", ""),
            item.get("descripcio_html", ""),
            item.get("municipi", ""),
            item.get("comarca", "")
        ))
        nuevos += 1  # Incrementar contador de eventos añadidos

    conn.commit()  # Guardar todos los cambios en la BD
    conn.close()
    flash(f"{nuevos} nuevos eventos añadidos.", "success")  # Mensaje de éxito
    return redirect(url_for("admin_panel"))  # Redirigir al panel de admin

# =============================================================================
# API: LISTADO PAGINADO CON FILTROS (PARA FRONTEND)
# =============================================================================
@app.route("/api/events")
def api_events():
    """
    Endpoint AJAX principal: devuelve eventos paginados con filtros combinados.
    Usado por events.html para carga dinámica con scroll infinito.
    """
    # Parámetros de paginación
    page = int(request.args.get("page", 1))  # Página actual (por defecto 1)
    per_page = int(request.args.get("per_page", 20))  # Eventos por página (por defecto 20)
    offset = (page - 1) * per_page  # Calcular offset para SQL LIMIT/OFFSET
    
    # Parámetros de filtrado (todos opcionales)
    query = request.args.get("q", "").strip().lower()  # Búsqueda textual
    date_from = request.args.get("date_from", "")      # Fecha desde
    date_to = request.args.get("date_to", "")          # Fecha hasta
    price_filter = request.args.get("price", "")       # 'free' o 'paid'
    category_filter = request.args.get("category", "") # Categoría cultural
    
    conn = get_db()
    c = conn.cursor()
    
    # Consulta base: seleccionamos los campos necesarios para el listado
    base_query = """
        SELECT id, denominacio, descripcio, imatges, data_inici, data_fi,
               horari, comarca_i_municipi, espai, entrades, url, tags_categories
        FROM events
    """
    
    conditions = []  # Lista para acumular condiciones WHERE
    params = []      # Lista para acumular parámetros de la consulta
    
    # --- APLICAR FILTROS ---
    
    # Filtro de búsqueda textual (busca en título, descripción, ubicación y espacio)
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
    
    # Filtro por precio (gratuito o de pago)
    if price_filter:
        if price_filter == "free":
            conditions.append("(entrades LIKE '%gratuit%' OR entrades LIKE '%gratis%' OR entrades LIKE '%gratuïta%')")
        elif price_filter == "paid":
            conditions.append("NOT (entrades LIKE '%gratuit%' OR entrades LIKE '%gratis%' OR entrades LIKE '%gratuïta%')")
    
    # Filtro por categoría cultural
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
    
    # --- CONSTRUIR CONSULTA FINAL ---
    if conditions:
        # Si hay filtros, añadimos cláusula WHERE con condiciones unidas por AND
        where_clause = " WHERE " + " AND ".join(conditions)
        count_query = "SELECT COUNT(*) FROM events" + where_clause  # Para contar total con filtros
        final_query = base_query + where_clause + " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([per_page, offset])  # Añadir límites de paginación a los parámetros
    else:
        # Si no hay filtros, consulta simple sin WHERE
        count_query = "SELECT COUNT(*) FROM events"
        final_query = base_query + " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params = [per_page, offset]
    
    # Ejecutar consulta principal para obtener eventos
    c.execute(final_query, params)
    rows = c.fetchall()
    
    # Ejecutar consulta para contar total (necesario para paginación en frontend)
    c.execute(count_query, params[:-2] if conditions else [])  # Excluir LIMIT/OFFSET del count
    total_count = c.fetchone()[0]
    
    conn.close()

    # Formatear resultados a lista de diccionarios para JSON
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
    return jsonify({"events": events, "total": total_count})  # Devolver JSON con eventos y total

# =============================================================================
# API: BÚSQUEDA RÁPIDA (SIMPLIFICADA)
# =============================================================================
@app.route("/api/search")
def api_search():
    """
    Endpoint AJAX para búsqueda rápida: devuelve hasta 100 resultados coincidentes.
    Usado para sugerencias o búsquedas en tiempo real.
    """
    query = request.args.get("q", "").strip().lower()  # Obtener término de búsqueda
    if not query:  # Si no hay query, devolver lista vacía
        return jsonify({"events": []})
    
    conn = get_db()
    c = conn.cursor()
    # Consulta con búsqueda en múltiples campos (título, descripción, ubicación, espacio)
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

    # Formatear resultados
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

# =============================================================================
# API: OBTENER OPCIONES DE FILTRO DISPONIBLES
# =============================================================================
@app.route("/api/filters")
def api_filters():
    """
    Endpoint AJAX: devuelve categorías disponibles y opciones de precio para los filtros.
    Usado para poblar dinámicamente los dropdowns del panel de filtros.
    """
    conn = get_db()
    c = conn.cursor()
    
    # Consultar categorías únicas presentes en los eventos (con mapeo simplificado)
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
    # Extraer categorías y filtrar 'altres'
    categories = [row["category"] for row in c.fetchall() if row["category"] != 'altres']
    
    conn.close()
    
    # Devolver JSON con categorías únicas (ordenadas) y opciones de precio
    return jsonify({
        "categories": sorted(set(categories)),  # Eliminar duplicados y ordenar
        "price_options": ["free", "paid"]       # Opciones fijas de precio
    })

# =============================================================================
# RUTA: FAVORITOS (PÚBLICA)
# =============================================================================
@app.route("/favorites")
def favorites():
    """
    Página de favoritos: muestra eventos marcados por el usuario.
    NOTA: Los favoritos se gestionan en frontend con localStorage, esta ruta solo renderiza la plantilla.
    """
    return render_template("favorites.html", title="Mis Favoritos")

# =============================================================================
# PUNTO DE ENTRADA PRINCIPAL (SOLO PARA DESARROLLO)
# =============================================================================
if __name__ == "__main__":
    """
    Este bloque solo se ejecuta si se corre app.py directamente (no mediante Apache/WSGI).
    Útil para pruebas locales con el servidor de desarrollo de Flask.
    """
    app.run(debug=True)  # Iniciar servidor con modo debug activado (recarga automática, errores detallados)
