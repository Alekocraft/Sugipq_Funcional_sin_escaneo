# -*- coding: utf-8 -*-
"""diagnostico_notificaciones.py

Ejecuta esto DESDE LA RAÍZ del proyecto (donde está app.py y el .env):

  python diagnostico_notificaciones.py --solicitud 2067
  python diagnostico_notificaciones.py --prestamo 123
  python diagnostico_notificaciones.py --test-email tu.correo@qualitascolombia.com.co

Qué hace:
- Carga .env
- Muestra configuración SMTP (sin exponer passwords)
- Prueba conexión SMTP (EHLO/NOOP)
- Lee aprobadores activos (tabla Aprobadores)
- Si pasas --solicitud: obtiene email del solicitante y muestra destinatarios calculados
- Si pasas --test-email: envía un correo de prueba usando NotificationService

NOTA: No imprime información sensible (passwords, tokens). Masking básico aplicado.
"""

from __future__ import annotations

import argparse
import os
import sys
import socket
import smtplib
from typing import List, Optional, Tuple


def _mask_email(email: str) -> str:
    if not email or "@" not in email:
        return "(vacío)"
    user, dom = email.split("@", 1)
    if len(user) <= 2:
        user_m = user[:1] + "*"
    else:
        user_m = user[:2] + "***" + user[-1:]
    return f"{user_m}@{dom}"


def _mask_value(v: str) -> str:
    if not v:
        return "(vacío)"
    if len(v) <= 4:
        return "****"
    return v[:2] + "***" + v[-2:]


def _load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(override=False)
    except Exception:
        # python-dotenv no instalado o falla; igual seguimos con os.environ
        pass


def _get_db_connection():
    # Import local (evita fallas si se ejecuta fuera del proyecto)
    try:
        from database import get_database_connection

        return get_database_connection()
    except Exception as e:
        print(f"[ERROR] No pude importar database.get_database_connection: {type(e).__name__}")
        return None


def _fetch_aprobadores_activos() -> List[Tuple[str, str]]:
    """Retorna lista [(nombre, email), ...] activos."""
    conn = _get_db_connection()
    if not conn:
        return []

    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT NombreAprobador, Email FROM Aprobadores WHERE Activo = 1 AND Email IS NOT NULL AND LTRIM(RTRIM(Email)) <> ''"
        )
        rows = cursor.fetchall() or []
        out: List[Tuple[str, str]] = []
        for r in rows:
            nombre = str(r[0] or "").strip() or "Aprobador"
            email = str(r[1] or "").strip()
            if email:
                out.append((nombre, email))
        return out
    except Exception as e:
        print(f"[ERROR] Consultando Aprobadores: {type(e).__name__}")
        return []
    finally:
        try:
            if cursor:
                cursor.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


def _fetch_solicitud_info(solicitud_id: int) -> Optional[dict]:
    """Replica (de forma simple) la info clave para notificaciones."""
    conn = _get_db_connection()
    if not conn:
        return None

    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                sm.SolicitudId,
                m.NombreElemento as material_nombre,
                sm.CantidadSolicitada,
                sm.CantidadEntregada,
                o.NombreOficina as oficina_nombre,
                sm.UsuarioSolicitante,
                u.CorreoElectronico as email_solicitante,
                es.NombreEstado as estado
            FROM SolicitudesMaterial sm
            INNER JOIN Materiales m ON sm.MaterialId = m.MaterialId
            INNER JOIN Oficinas o ON sm.OficinaSolicitanteId = o.OficinaId
            LEFT JOIN Usuarios u ON sm.UsuarioSolicitante = u.NombreUsuario
            INNER JOIN EstadosSolicitud es ON sm.EstadoId = es.EstadoId
            WHERE sm.SolicitudId = ?
            """,
            (solicitud_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "material_nombre": row[1],
            "cantidad_solicitada": row[2],
            "cantidad_entregada": row[3],
            "oficina_nombre": row[4],
            "usuario_solicitante": row[5],
            "email_solicitante": row[6],
            "estado": row[7],
        }
    except Exception as e:
        print(f"[ERROR] Consultando Solicitud: {type(e).__name__}")
        return None
    finally:
        try:
            if cursor:
                cursor.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


def _smtp_smoke_test(server: str, port: int, use_tls: bool = False, user: str = "", pwd: str = "") -> bool:
    try:
        smtp = smtplib.SMTP(server, port, timeout=10)
        smtp.ehlo()
        if use_tls:
            smtp.starttls()
            smtp.ehlo()
        if user and pwd:
            smtp.login(user, pwd)
        code, msg = smtp.noop()
        smtp.quit()
        ok = int(code) == 250
        print(f"[SMTP] NOOP => {code} {msg!r} (ok={ok})")
        return ok
    except Exception as e:
        print(f"[SMTP] ERROR: {type(e).__name__}: {e}")
        return False


def _send_test_email(to_email: str) -> bool:
    try:
        # Importa el servicio real
        from services.notification_service import NotificationService

        asunto = "[DIAGNÓSTICO] Prueba de envío SMTP desde SUGIP"
        html = "<p>Si estás leyendo esto, el envío SMTP desde la app está funcionando.</p>"
        txt = "Prueba SMTP desde SUGIP."
        ok = NotificationService.enviar_notificacion_general(to_email, to_email, asunto, html, txt)
        print(f"[SEND] enviar_notificacion_general => {ok}")
        return bool(ok)
    except Exception as e:
        print(f"[SEND] ERROR: {type(e).__name__}: {e}")
        return False


def main() -> int:
    _load_dotenv_if_available()

    parser = argparse.ArgumentParser()
    parser.add_argument("--solicitud", type=int, default=0, help="ID de solicitud a diagnosticar")
    parser.add_argument("--prestamo", type=int, default=0, help="ID de préstamo (solo muestra que el script corre)")
    parser.add_argument("--test-email", type=str, default="", help="Enviar correo de prueba a este email")
    args = parser.parse_args()

    print("=== DIAGNÓSTICO NOTIFICACIONES (SUGIP) ===")

    smtp_server = os.getenv("SMTP_SERVER", "").strip()
    smtp_port = int((os.getenv("SMTP_PORT", "25") or "25").strip())
    smtp_from = os.getenv("SMTP_FROM_EMAIL", "").strip()
    smtp_tls = (os.getenv("SMTP_USE_TLS", "False").strip().lower() == "true")
    smtp_user = os.getenv("SMTP_USERNAME", "").strip()
    smtp_pwd = os.getenv("SMTP_PASSWORD", "").strip()
    notif_enabled = (os.getenv("NOTIFICATIONS_ENABLED", "true").strip().lower() not in ("0", "false", "no", "n"))

    print(f"NOTIFICATIONS_ENABLED: {notif_enabled}")
    print(f"SMTP_SERVER: {smtp_server}")
    print(f"SMTP_PORT: {smtp_port}")
    print(f"SMTP_USE_TLS: {smtp_tls}")
    print(f"SMTP_FROM_EMAIL: {_mask_email(smtp_from)}")
    if smtp_user:
        print(f"SMTP_USERNAME: {_mask_value(smtp_user)}")
    if smtp_pwd:
        print("SMTP_PASSWORD: (configurado)")

    # Resolución DNS (solo para ver si resuelve; si es IP, no pasa nada)
    try:
        socket.gethostbyname(smtp_server)
        print("[DNS] OK")
    except Exception:
        print("[DNS] No resolvió (si es IP, es normal)")

    print("\n--- Prueba SMTP (conexión) ---")
    if smtp_server:
        _smtp_smoke_test(smtp_server, smtp_port, smtp_tls, smtp_user, smtp_pwd)
    else:
        print("[SMTP] SMTP_SERVER vacío")

    print("\n--- Aprobadores activos (tabla Aprobadores) ---")
    aprobadores = _fetch_aprobadores_activos()
    if not aprobadores:
        print("(sin aprobadores o no se pudo consultar la tabla)")
    else:
        for n, e in aprobadores:
            print(f"- {n}: {_mask_email(e)}")

    if args.solicitud:
        print(f"\n--- Solicitud #{args.solicitud} ---")
        info = _fetch_solicitud_info(args.solicitud)
        if not info:
            print("No se encontró la solicitud o no se pudo consultar")
        else:
            solicitante_email = (info.get("email_solicitante") or "").strip()
            print(f"Solicitante: {info.get('usuario_solicitante')} | email: {_mask_email(solicitante_email)}")
            dests = []
            if solicitante_email:
                dests.append(solicitante_email)
            dests.extend([e for _, e in aprobadores])
            # dedup
            dests = sorted({d.strip().lower(): d.strip() for d in dests if d and d.strip()}.values())
            print("Destinatarios esperados (solicitante + aprobadores):")
            for d in dests:
                print(f"  - {_mask_email(d)}")

    if args.test_email:
        print("\n--- Envío de prueba (NotificationService.enviar_notificacion_general) ---")
        _send_test_email(args.test_email.strip())

    print("\n=== FIN DIAGNÓSTICO ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
