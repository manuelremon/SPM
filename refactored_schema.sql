-- Refactored SQLite Schema for SPM-2 Project
-- This schema enforces data integrity, normalization, and proper constraints.

-- Catalog table for roles
CREATE TABLE roles (
    id_rol INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_rol TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Centers table (unchanged, but ensure FKs point correctly)
CREATE TABLE centros (
    id_centro TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    ubicacion TEXT,
    responsable TEXT,
    activo INTEGER DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Warehouses table (existing FK to centros)
CREATE TABLE almacenes (
    id_almacen TEXT PRIMARY KEY,
    id_centro TEXT NOT NULL,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    responsable TEXT,
    activo INTEGER DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_centro) REFERENCES centros(id_centro) ON DELETE RESTRICT ON UPDATE CASCADE
);

-- Materials table (add FK to centros)
CREATE TABLE materiales (
    codigo TEXT PRIMARY KEY,
    descripcion TEXT NOT NULL,
    descripcion_larga TEXT,
    centro TEXT,
    sector TEXT,
    unidad TEXT,
    precio_usd REAL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (centro) REFERENCES centros(id_centro) ON DELETE RESTRICT ON UPDATE CASCADE
);

-- Users table (remove centros and rol, add constraints)
CREATE TABLE usuarios (
    id_spm TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    apellido TEXT NOT NULL,
    contrasena TEXT NOT NULL CHECK (LENGTH(contrasena) > 0),
    mail TEXT UNIQUE,
    posicion TEXT,
    sector TEXT,
    jefe TEXT,
    gerente1 TEXT,
    gerente2 TEXT,
    telefono TEXT,
    estado_registro TEXT,
    id_ypf TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (jefe) REFERENCES usuarios(id_spm) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (gerente1) REFERENCES usuarios(id_spm) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (gerente2) REFERENCES usuarios(id_spm) ON DELETE RESTRICT ON UPDATE CASCADE
);

-- Junction table for user-centers
CREATE TABLE usuario_centros (
    id_usuario_centro INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id TEXT NOT NULL,
    centro_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id_spm) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (centro_id) REFERENCES centros(id_centro) ON DELETE CASCADE ON UPDATE CASCADE,
    UNIQUE (usuario_id, centro_id)
);

-- Junction table for user-roles
CREATE TABLE usuario_roles (
    id_usuario_rol INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id TEXT NOT NULL,
    rol_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id_spm) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (rol_id) REFERENCES roles(id_rol) ON DELETE CASCADE ON UPDATE CASCADE,
    UNIQUE (usuario_id, rol_id)
);

-- Requests table (add FKs, remove data_json, add CHECK to status)
CREATE TABLE solicitudes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_usuario TEXT NOT NULL,
    centro TEXT NOT NULL,
    sector TEXT NOT NULL,
    justificacion TEXT NOT NULL,
    centro_costos TEXT,
    almacen_virtual TEXT,
    criticidad TEXT NOT NULL DEFAULT 'Normal',
    fecha_necesidad TEXT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'pending_approval', 'approved', 'rejected', 'in_process', 'completed')),
    aprobador_id TEXT,
    planner_id TEXT,
    total_monto REAL DEFAULT 0,
    notificado_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id_spm) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (centro) REFERENCES centros(id_centro) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (aprobador_id) REFERENCES usuarios(id_spm) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (planner_id) REFERENCES usuarios(id_spm) ON DELETE RESTRICT ON UPDATE CASCADE
);

-- Request items table (normalized from data_json)
CREATE TABLE solicitud_items (
    id_item INTEGER PRIMARY KEY AUTOINCREMENT,
    solicitud_id INTEGER NOT NULL,
    material_codigo TEXT NOT NULL,
    cantidad REAL NOT NULL,
    precio_unitario REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (solicitud_id) REFERENCES solicitudes(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (material_codigo) REFERENCES materiales(codigo) ON DELETE RESTRICT ON UPDATE CASCADE,
    UNIQUE (solicitud_id, material_codigo)
);

-- Planner assignments table (change FK to usuarios, remove planificadores reference)
CREATE TABLE planificador_asignaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    planificador_id TEXT NOT NULL,
    centro TEXT,
    sector TEXT,
    almacen_virtual TEXT,
    prioridad INTEGER DEFAULT 1,
    activo INTEGER DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (planificador_id) REFERENCES usuarios(id_spm) ON DELETE RESTRICT ON UPDATE CASCADE,
    UNIQUE (planificador_id, centro, sector, almacen_virtual)
);

-- Indexes for performance (optional but recommended)
CREATE INDEX idx_solicitudes_id_usuario ON solicitudes(id_usuario);
CREATE INDEX idx_solicitudes_centro ON solicitudes(centro);
CREATE INDEX idx_solicitudes_status ON solicitudes(status);
CREATE INDEX idx_solicitud_items_solicitud_id ON solicitud_items(solicitud_id);
CREATE INDEX idx_usuario_centros_usuario_id ON usuario_centros(usuario_id);
CREATE INDEX idx_usuario_roles_usuario_id ON usuario_roles(usuario_id);