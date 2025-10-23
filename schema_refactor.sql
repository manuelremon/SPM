/*
Act as an expert Senior Database Architect. Your task is to perform a critical refactoring of the provided SQLite schema. The current schema lacks data integrity, normalization, and proper constraints, leading to potential data corruption.

Your goal is to generate a new, complete, and robust SQL schema that fixes all the identified issues.

-------------------------------
-- CURRENT (FLAWED) SCHEMA --
-------------------------------

CREATE TABLE almacenes (
    id_almacen TEXT PRIMARY KEY,
    id_centro TEXT NOT NULL,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    responsable TEXT,
    activo INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_centro) REFERENCES centros(id_centro)
);

CREATE TABLE centros (
    id_centro TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    ubicacion TEXT,
    responsable TEXT,
    activo INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE materiales(
    codigo TEXT PRIMARY KEY,
    descripcion TEXT NOT NULL,
    descripcion_larga TEXT,
    centro TEXT, -- FLAW: Should be a Foreign Key
    sector TEXT,
    unidad TEXT,
    precio_usd REAL DEFAULT 0
);

CREATE TABLE solicitudes(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_usuario TEXT NOT NULL, -- FLAW: Should be a Foreign Key
    centro TEXT NOT NULL, -- FLAW: Should be a Foreign Key
    sector TEXT NOT NULL,
    justificacion TEXT NOT NULL,
    centro_costos TEXT,
    almacen_virtual TEXT,
    criticidad TEXT NOT NULL DEFAULT 'Normal',
    fecha_necesidad TEXT,
    data_json TEXT NOT NULL, -- FLAW: Denormalized. Must be a new table.
    status TEXT NOT NULL DEFAULT 'draft',
    aprobador_id TEXT, -- FLAW: Should be a Foreign Key
    planner_id TEXT, -- FLAW: Should be a Foreign Key
    total_monto REAL DEFAULT 0,
    notificado_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE planificador_asignaciones(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    planificador_id TEXT NOT NULL, -- FLAW: Should be a Foreign Key
    centro TEXT,
    sector TEXT,
    almacen_virtual TEXT,
    prioridad INTEGER DEFAULT 1,
    activo BOOLEAN DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(planificador_id) REFERENCES planificadores(usuario_id),
    UNIQUE(planificador_id, centro, sector, almacen_virtual)
);

CREATE TABLE planificadores(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id TEXT NOT NULL UNIQUE,
    nombre TEXT NOT NULL,
    activo BOOLEAN DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(usuario_id) REFERENCES usuarios(id_spm)
);

CREATE TABLE usuarios(
    id_spm TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    apellido TEXT NOT NULL,
    rol TEXT NOT NULL DEFAULT 'Solicitante', -- FLAW: Denormalized. Must be a new table.
    contrasena TEXT NOT NULL, -- FLAW: Must store a HASH, not plaintext.
    mail TEXT, -- FLAW: Should be UNIQUE
    posicion TEXT,
    sector TEXT,
    centros TEXT, -- FLAW: Denormalized. Must be a new table.
    jefe TEXT, -- FLAW: Should be a Foreign Key
    gerente1 TEXT, -- FLAW: Should be a Foreign Key
    gerente2 TEXT, -- FLAW: Should be a Foreign Key
    telefono TEXT,
    estado_registro TEXT,
    id_ypf TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

---------------------------------------
-- DETAILED REFACTORING INSTRUCTIONS --
---------------------------------------

Generate the new, complete SQL schema (CREATE TABLE statements) applying the following fixes:

1.  **Enforce Full Foreign Key (FK) Integrity:**
    * Add `ON DELETE RESTRICT ON UPDATE CASCADE` to all new and existing FK constraints.
    * `solicitudes.id_usuario` -> `usuarios(id_spm)`
    * `solicitudes.centro` -> `centros(id_centro)`
    * `solicitudes.aprobador_id` -> `usuarios(id_spm)` (Allow NULL)
    * `solicitudes.planner_id` -> `usuarios(id_spm)` (Allow NULL)
    * `materiales.centro` -> `centros(id_centro)` (Allow NULL)
    * `usuarios.jefe` -> `usuarios(id_spm)` (Self-referencing, Allow NULL)
    * `usuarios.gerente1` -> `usuarios(id_spm)` (Self-referencing, Allow NULL)
    * `usuarios.gerente2` -> `usuarios(id_spm)` (Self-referencing, Allow NULL)
    * `planificador_asignaciones.planificador_id` -> `usuarios(id_spm)` (The `planificadores` table is redundant if a user can just have a 'Planificador' role. Remove the `planificadores` table and link `planificador_asignaciones` directly to `usuarios(id_spm)`).

2.  **Normalize Denormalized Fields:**

    * **Problem:** `usuarios.centros` (e.g., "1008,1050")
    * **Solution:** Remove the `centros` column from `usuarios`. Create a new junction table:
        ```sql
        CREATE TABLE usuario_centros (
            id_usuario_centro INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id TEXT NOT NULL,
            centro_id TEXT NOT NULL,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id_spm) ON DELETE CASCADE,
            FOREIGN KEY(centro_id) REFERENCES centros(id_centro) ON DELETE CASCADE,
            UNIQUE(usuario_id, centro_id)
        );
        ```

    * **Problem:** `usuarios.rol` (e.g., "Solicitante, Aprobador")
    * **Solution:** Remove the `rol` column from `usuarios`. Create a `roles` catalog table and a `usuario_roles` junction table:
        ```sql
        CREATE TABLE roles (
            id_rol INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_rol TEXT NOT NULL UNIQUE
        );
        
        CREATE TABLE usuario_roles (
            id_usuario_rol INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id TEXT NOT NULL,
            rol_id INTEGER NOT NULL,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id_spm) ON DELETE CASCADE,
            FOREIGN KEY(rol_id) REFERENCES roles(id_rol) ON DELETE CASCADE,
            UNIQUE(usuario_id, rol_id)
        );
        ```

    * **Problem:** `solicitudes.data_json` (Stores the list of materials).
    * **Solution:** Remove the `data_json` column from `solicitudes`. Create a new `solicitud_items` table:
        ```sql
        CREATE TABLE solicitud_items (
            id_item INTEGER PRIMARY KEY AUTOINCREMENT,
            solicitud_id INTEGER NOT NULL,
            material_codigo TEXT NOT NULL,
            cantidad REAL NOT NULL,
            precio_unitario REAL, -- Capture price at time of request
            FOREIGN KEY(solicitud_id) REFERENCES solicitudes(id) ON DELETE CASCADE,
            FOREIGN KEY(material_codigo) REFERENCES materiales(codigo) ON DELETE RESTRICT,
            UNIQUE(solicitud_id, material_codigo)
        );
        ```

3.  **Clean up Redundancy:**
    * Remove the `planificadores` table. The 'Planificador' status should be handled by the new `usuario_roles` table.
    * Update `planificador_asignaciones.planificador_id` to point directly to `usuarios(id_spm)`.

4.  **Add Necessary Constraints:**
    * Add `UNIQUE` constraint to `usuarios.mail`.
    * Add `CHECK` constraint to `usuarios.contrasena` to ensure it's not empty (`LENGTH(contrasena) > 0`). (We can't enforce hashing at the DB level, but we can prevent empty strings).
    * Add `CHECK` constraint to `solicitudes.status` to limit values (e.g., 'draft', 'pending_approval', 'approved', 'rejected', 'in_process', 'completed').
    * Change `planificador_asignaciones.activo` from `BOOLEAN` to `INTEGER DEFAULT 1` for SQLite compatibility.

5.  **Data Type Optimization (Optional but Recommended):**
    * Where possible, change `TEXT` PRIMARY KEYS (like `centros.id_centro`) to `INTEGER PRIMARY KEY` if they are not natural keys (like `materiales.codigo`). For this exercise, you can keep the `TEXT` PKs to minimize breaking changes, but ensure all FKs pointing to them are also `TEXT`.

Please generate the complete, final list of `CREATE TABLE` statements for the refactored schema based on all instructions above.
*/