CREATE TABLE events (
    id TEXT PRIMARY KEY,
    version TEXT,
    created_at TEXT,
    updated_at TEXT,
    codi TEXT,
    data_fi TEXT,
    data_inici TEXT,
    denominacio TEXT,
    subtitol TEXT,
    descripcio TEXT,
    tags_ambits TEXT,
    tags_categories TEXT,
    entrades TEXT,
    horari TEXT,
    links TEXT,
    imatges TEXT,
    adreca TEXT,
    comarca_i_municipi TEXT,
    espai TEXT,
    latitud TEXT,
    longitud TEXT,
    telefon TEXT,
    url TEXT,
    imgapp TEXT,
    descripcio_html TEXT,
    municipi TEXT,
    comarca TEXT
);

CREATE TABLE admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE sqlite_sequence(name,seq);
