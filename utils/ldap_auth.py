# -*- coding: utf-8 -*-
"""Utilidades de autenticación y búsqueda LDAP/AD.

Compatibilidad:
- Se expone una instancia `ad_auth` de `ADAuth`.
- Métodos: test_connection, authenticate_user, search_user_by_name, search_user_by_email,
  get_user_details.

Mejoras de robustez/seguridad:
- Sin recursión ante LDAPSocketOpenError (se prueban opciones y se corta).
- Escapado de filtros LDAP para evitar inyección.
- Logs sanitizados.
- FIX: El bind de servicio ahora normaliza usuario (DOMINIO\\user) y hace fallback a SIMPLE (user@dominio)
  para evitar errores tipo LDAPUnknownAuthenticationMethodError cuando LDAP_SERVICE_USER viene sin dominio.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from ldap3 import ALL, NTLM, SIMPLE, SUBTREE, Connection, Server
from ldap3.core.exceptions import (
    LDAPBindError,
    LDAPException,
    LDAPSocketOpenError,
    LDAPUnknownAuthenticationMethodError,
)
from ldap3.utils.conv import escape_filter_chars

logger = logging.getLogger(__name__)


# =========================
# Imports tolerantes
# =========================
try:
    from config.config import Config  # type: ignore
except Exception:
    try:
        from config import Config  # type: ignore
    except Exception:

        class Config:  # fallback mínimo
            LDAP_ENABLED = True
            LDAP_SERVER = os.getenv("LDAP_SERVER", "")
            LDAP_PORT = int(os.getenv("LDAP_PORT", "389"))
            LDAP_DOMAIN = os.getenv("LDAP_DOMAIN", "")
            LDAP_SEARCH_BASE = os.getenv("LDAP_SEARCH_BASE", "")
            LDAP_SERVICE_USER = os.getenv("LDAP_SERVICE_USER")
            LDAP_SERVICE_PASSWORD = os.getenv("LDAP_SERVICE_PASSWORD")


try:
    from utils.helpers import sanitizar_username, sanitizar_log_text  # type: ignore
except Exception:
    from helpers import sanitizar_username, sanitizar_log_text  # type: ignore


@dataclass(frozen=True)
class _LdapEndpoint:
    port: int
    use_ssl: bool


def _bool_env(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


class ADAuth:
    """Cliente LDAP simple para autenticación y búsquedas."""

    def __init__(self):
        self.server_address: str = getattr(Config, "LDAP_SERVER", os.getenv("LDAP_SERVER", ""))
        try:
            self.port: int = int(getattr(Config, "LDAP_PORT", os.getenv("LDAP_PORT", "389")))
        except Exception:
            self.port = 389

        self.domain: str = getattr(Config, "LDAP_DOMAIN", os.getenv("LDAP_DOMAIN", ""))
        self.search_base: str = getattr(Config, "LDAP_SEARCH_BASE", os.getenv("LDAP_SEARCH_BASE", ""))

        self.service_user: Optional[str] = getattr(
            Config, "LDAP_SERVICE_USER", os.getenv("LDAP_SERVICE_USER")
        )
        self.service_password: Optional[str] = getattr(
            Config, "LDAP_SERVICE_PASSWORD", os.getenv("LDAP_SERVICE_PASSWORD")
        )

        # Permite forzar SSL desde env si existe
        self.force_ssl: Optional[bool] = None
        if os.getenv("LDAP_USE_SSL") is not None:
            self.force_ssl = _bool_env("LDAP_USE_SSL", default=False)

        # Timeout de conexión
        try:
            self.connect_timeout = int(os.getenv("LDAP_CONNECT_TIMEOUT", "10"))
        except Exception:
            self.connect_timeout = 10

        # Recordar el último endpoint que funcionó
        self._last_good: Optional[_LdapEndpoint] = None

    # ---------------------
    # Helpers
    # ---------------------

    def _endpoints_to_try(self) -> List[_LdapEndpoint]:
        """Lista ordenada de endpoints (puerto/ssl) a intentar."""
        if not self.server_address:
            return []

        endpoints: List[_LdapEndpoint] = []

        # 1) último bueno
        if self._last_good:
            endpoints.append(self._last_good)

        # 2) config principal
        use_ssl_primary = (self.force_ssl if self.force_ssl is not None else (self.port == 636))
        endpoints.append(_LdapEndpoint(port=self.port, use_ssl=use_ssl_primary))

        # 3) fallback comunes
        if self.port != 389:
            endpoints.append(_LdapEndpoint(port=389, use_ssl=False))
        if self.port != 636:
            endpoints.append(_LdapEndpoint(port=636, use_ssl=True))

        # dedupe preservando orden
        seen = set()
        uniq: List[_LdapEndpoint] = []
        for ep in endpoints:
            key = (ep.port, ep.use_ssl)
            if key not in seen:
                seen.add(key)
                uniq.append(ep)
        return uniq

    def _make_server(self, ep: _LdapEndpoint) -> Server:
        return Server(
            self.server_address,
            port=ep.port,
            use_ssl=ep.use_ssl,
            get_info=ALL,
            connect_timeout=self.connect_timeout,
        )

    def _format_user_for_ntlm(self, user: str) -> str:
        """Devuelve el usuario en formato DOMINIO\\usuario si aplica."""
        u = (user or "").strip()
        if not u:
            return u
        if "\\" in u or "@" in u:
            return u
        return f"{self.domain}\\{u}" if self.domain else u

    def _format_user_for_simple(self, user: str) -> str:
        """Devuelve el usuario preferiblemente en formato UPN (usuario@dominio)."""
        u = (user or "").strip()
        if not u:
            return u
        if "@" in u:
            return u
        if "\\" in u:
            # DOMAIN\\user -> user
            u = u.split("\\", 1)[1]
        if self.domain and "." in self.domain:
            return f"{u}@{self.domain}"
        return u

    def _service_bind(self, server: Server) -> Optional[Connection]:
        """Bind con cuenta de servicio para búsquedas.

        FIX clave: si LDAP_SERVICE_USER viene sin dominio (ej: 'userauge'), NTLM falla.
        Aquí normalizamos a DOMINIO\\user y si falla intentamos SIMPLE con user@dominio.
        """
        if not self.service_user or not self.service_password:
            return None

        principal_ntlm = self._format_user_for_ntlm(self.service_user)
        principal_simple = self._format_user_for_simple(self.service_user)

        last_error: str | None = None

        for auth_name, auth_method, principal in (
            ("NTLM", NTLM, principal_ntlm),
            ("SIMPLE", SIMPLE, principal_simple),
        ):
            try:
                conn = Connection(
                    server,
                    user=principal,
                    password=self.service_password,
                    authentication=auth_method,
                    auto_bind=True,
                )
                return conn

            except LDAPSocketOpenError:
                raise
            except (LDAPUnknownAuthenticationMethodError, LDAPBindError, LDAPException) as e:
                last_error = f"{type(e).__name__} ({auth_name})"
                continue
            except Exception as e:
                last_error = f"{type(e).__name__} ({auth_name})"
                continue

        logger.error(
            "❌ LDAP: Error autenticando con cuenta de servicio: %s",
            sanitizar_log_text(last_error or "Unknown"),
        )
        return None

    # ---------------------
    # API pública
    # ---------------------

    def test_connection(self) -> Dict[str, object]:
        """Prueba apertura de socket (y bind si hay cuenta de servicio)."""
        if not getattr(Config, "LDAP_ENABLED", True):
            return {"success": False, "message": "LDAP deshabilitado"}

        if not self.server_address:
            return {"success": False, "message": "LDAP_SERVER no configurado"}

        last_err: Optional[str] = None
        for ep in self._endpoints_to_try():
            try:
                server = self._make_server(ep)

                if self.service_user and self.service_password:
                    conn = self._service_bind(server)
                    if conn:
                        conn.unbind()
                        self._last_good = ep
                        return {
                            "success": True,
                            "message": "Conexión LDAP exitosa",
                            "server": self.server_address,
                            "port": ep.port,
                            "use_ssl": ep.use_ssl,
                        }
                    last_err = "Bind de servicio falló"
                else:
                    conn = Connection(server, auto_bind=False)
                    if conn.open():
                        conn.unbind()
                        self._last_good = ep
                        return {
                            "success": True,
                            "message": "Socket LDAP accesible",
                            "server": self.server_address,
                            "port": ep.port,
                            "use_ssl": ep.use_ssl,
                        }
                    last_err = "No se pudo abrir socket"

            except LDAPSocketOpenError:
                last_err = f"No se pudo abrir socket ({ep.port}, ssl={ep.use_ssl})"
                continue
            except Exception as e:
                last_err = f"Error: {type(e).__name__}"
                continue

        return {"success": False, "message": last_err or "No se pudo conectar a LDAP"}

    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, str]]:
        """Autentica un usuario contra AD. Retorna dict con info mínima o None."""
        if not getattr(Config, "LDAP_ENABLED", True):
            return None

        username_clean = (username or "").strip()
        if not username_clean or not password:
            return None

        user_principal = self._format_user_for_ntlm(username_clean)

        last_error: Optional[str] = None

        for ep in self._endpoints_to_try():
            try:
                server = self._make_server(ep)
                conn = Connection(
                    server,
                    user=user_principal,
                    password=password,
                    authentication=NTLM,
                    auto_bind=True,
                )

                info = self.get_user_details(username_clean, conn=conn) or {}
                conn.unbind()

                self._last_good = ep

                return {
                    "username": username_clean,
                    "nombre": info.get("nombre") or username_clean,
                    "email": info.get("email") or "",
                }

            except LDAPSocketOpenError:
                last_error = f"LDAPSocketOpenError ({ep.port}, ssl={ep.use_ssl})"
                continue
            except LDAPBindError:
                last_error = "LDAPBindError"
                break
            except LDAPException as e:
                last_error = type(e).__name__
                break
            except Exception as e:
                last_error = type(e).__name__
                break

        logger.error(
            "❌ LDAP: Falló autenticación para %s: [error](%s)",
            sanitizar_username(username_clean),
            last_error or "Unknown",
        )
        return None

    def search_user_by_name(self, name: str, max_results: int = 20) -> List[Dict[str, str]]:
        """Busca usuarios por nombre (displayName) o sAMAccountName."""
        term = (name or "").strip()
        if not term:
            return []

        safe_term = escape_filter_chars(term)
        ldap_filter = f"(|(displayName=*{safe_term}*)(sAMAccountName=*{safe_term}*))"

        return self._search_users(ldap_filter, max_results=max_results)

    def search_user_by_email(self, email: str, max_results: int = 20) -> List[Dict[str, str]]:
        """Busca usuarios por correo."""
        term = (email or "").strip()
        if not term:
            return []

        safe_term = escape_filter_chars(term)
        ldap_filter = f"(mail=*{safe_term}*)"

        return self._search_users(ldap_filter, max_results=max_results)

    def _search_users(self, ldap_filter: str, max_results: int = 20) -> List[Dict[str, str]]:
        if not self.search_base:
            logger.error("LDAP_SEARCH_BASE no configurado")
            return []

        last_error: Optional[str] = None

        for ep in self._endpoints_to_try():
            try:
                server = self._make_server(ep)

                conn = self._service_bind(server)
                if conn is None:
                    last_error = "Bind de servicio falló"
                    break

                attrs = [
                    "sAMAccountName",
                    "displayName",
                    "mail",
                    "department",
                    "title",
                    "distinguishedName",
                ]

                conn.search(
                    search_base=self.search_base,
                    search_filter=ldap_filter,
                    search_scope=SUBTREE,
                    attributes=attrs,
                    size_limit=max_results,
                )

                results: List[Dict[str, str]] = []
                for entry in conn.entries:
                    results.append(
                        {
                            "usuario": str(getattr(entry, "sAMAccountName", "") or ""),
                            "nombre": str(getattr(entry, "displayName", "") or ""),
                            "email": str(getattr(entry, "mail", "") or ""),
                            "departamento": str(getattr(entry, "department", "") or ""),
                            "cargo": str(getattr(entry, "title", "") or ""),
                            "dn": str(getattr(entry, "distinguishedName", "") or ""),
                        }
                    )

                conn.unbind()
                self._last_good = ep
                return results

            except LDAPSocketOpenError:
                last_error = f"LDAPSocketOpenError ({ep.port}, ssl={ep.use_ssl})"
                continue
            except Exception as e:
                last_error = type(e).__name__
                logger.error("❌ LDAP: Error buscando usuarios: [error](%s)", type(e).__name__)
                break

        if last_error:
            logger.error("❌ LDAP: Búsqueda falló: %s", sanitizar_log_text(last_error))
        return []

    def get_user_details(self, username: str, conn: Optional[Connection] = None) -> Optional[Dict[str, str]]:
        """Obtiene detalles del usuario."""
        user = (username or "").strip()
        if not user or not self.search_base:
            return None

        safe_user = escape_filter_chars(user)
        ldap_filter = f"(sAMAccountName={safe_user})"

        if conn is not None:
            try:
                conn.search(
                    search_base=self.search_base,
                    search_filter=ldap_filter,
                    search_scope=SUBTREE,
                    attributes=["displayName", "mail", "department", "title"],
                    size_limit=1,
                )
                if not conn.entries:
                    return None
                entry = conn.entries[0]
                return {
                    "nombre": str(getattr(entry, "displayName", "") or ""),
                    "email": str(getattr(entry, "mail", "") or ""),
                    "departamento": str(getattr(entry, "department", "") or ""),
                    "cargo": str(getattr(entry, "title", "") or ""),
                }
            except Exception:
                return None

        for ep in self._endpoints_to_try():
            try:
                server = self._make_server(ep)
                service_conn = self._service_bind(server)
                if service_conn is None:
                    return None

                service_conn.search(
                    search_base=self.search_base,
                    search_filter=ldap_filter,
                    search_scope=SUBTREE,
                    attributes=["displayName", "mail", "department", "title"],
                    size_limit=1,
                )

                if not service_conn.entries:
                    service_conn.unbind()
                    return None

                entry = service_conn.entries[0]
                data = {
                    "nombre": str(getattr(entry, "displayName", "") or ""),
                    "email": str(getattr(entry, "mail", "") or ""),
                    "departamento": str(getattr(entry, "department", "") or ""),
                    "cargo": str(getattr(entry, "title", "") or ""),
                }

                service_conn.unbind()
                self._last_good = ep
                return data

            except LDAPSocketOpenError:
                continue
            except Exception:
                break

        return None


# Instancia global usada por el resto de la app
ad_auth = ADAuth()
