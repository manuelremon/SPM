#!/usr/bin/env python3
"""
Script para actualizar solicitudes existentes que no tienen aprobador_id asignado.
"""

import sys
import os

# Agregar el directorio src al path
script_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(script_dir)
sys.path.insert(0, os.path.join(parent_dir, 'src'))

from backend.db import get_connection

def _coerce_str(value: any) -> str | None:
    if value is None:
        return None
    return str(value).strip()

def _resolve_approver(con, user: dict | None, total_monto: float = 0.0) -> str | None:
    if not user:
        return None
    
    # Determinar el aprobador basado en el monto total
    if total_monto <= 20000.0:
        # Jefe desde USD 0.01 hasta USD 20000
        approver_field = "jefe"
    elif total_monto <= 100000.0:
        # Gerente1 desde USD 20000.01 hasta USD 100000
        approver_field = "gerente1"
    else:
        # Gerente2 desde USD 100000.01 en adelante
        approver_field = "gerente2"
    
    approver_email = _coerce_str(user.get(approver_field))
    if approver_email:
        # Buscar el id_spm del usuario con este email
        approver_user = con.execute(
            "SELECT id_spm FROM usuarios WHERE lower(mail) = ?",
            (approver_email.lower(),)
        ).fetchone()
        if approver_user:
            return approver_user["id_spm"]
    
    # Fallback: buscar en otros campos si el campo específico no está disponible
    for field in ("jefe", "gerente1", "gerente2"):
        approver_email = _coerce_str(user.get(field))
        if approver_email:
            approver_user = con.execute(
                "SELECT id_spm FROM usuarios WHERE lower(mail) = ?",
                (approver_email.lower(),)
            ).fetchone()
            if approver_user:
                return approver_user["id_spm"]
    return None

def update_existing_solicitudes():
    """Actualizar solicitudes existentes sin aprobador_id."""
    with get_connection() as con:
        # Obtener solicitudes sin aprobador_id
        solicitudes = con.execute('''
            SELECT s.id, s.id_usuario, s.total_monto, u.nombre, u.jefe, u.gerente1, u.gerente2
            FROM solicitudes s
            JOIN usuarios u ON lower(s.id_usuario) = lower(u.id_spm)
            WHERE s.aprobador_id IS NULL
        ''').fetchall()

        print(f"Encontradas {len(solicitudes)} solicitudes sin aprobador_id")

        for solicitud in solicitudes:
            user = {
                'jefe': solicitud['jefe'],
                'gerente1': solicitud['gerente1'],
                'gerente2': solicitud['gerente2']
            }
            aprobador_id = _resolve_approver(con, user, solicitud['total_monto'])

            if aprobador_id:
                con.execute('''
                    UPDATE solicitudes
                    SET aprobador_id = ?, updated_at = datetime('now')
                    WHERE id = ?
                ''', (aprobador_id, solicitud['id']))
                print(f"Actualizada solicitud {solicitud['id']}: aprobador_id = {aprobador_id}")
            else:
                print(f"No se pudo determinar aprobador para solicitud {solicitud['id']}")

        con.commit()

if __name__ == '__main__':
    update_existing_solicitudes()