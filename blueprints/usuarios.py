# blueprints/usuarios.py 
from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify
from functools import wraps
from models.usuarios_model import UsuarioModel
from database import get_database_connection
import logging
from config.config import Config  
# ✅ CORRECCIÓN: Importar funciones de sanitización
from utils.helpers import sanitizar_email, sanitizar_username, sanitizar_ip, sanitizar_identificacion

logger = logging.getLogger(__name__)

usuarios_bp = Blueprint('usuarios', __name__, url_prefix='/usuarios')

# ======================
# DECORADORES
# ======================

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            flash('Debe iniciar sesión para acceder a esta página', 'danger')
            return redirect(url_for('auth_bp.login'))
        
        # CORRECCIÓN: "admin" equivale a "administrador"
        rol_actual = session.get('rol', '').lower()
        if rol_actual not in ['administrador', 'admin']:
            flash('No tiene permisos de administrador para acceder a esta página', 'danger')
            return redirect(url_for('dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function

# ======================
# RUTAS DE GESTIÓN DE USUARIOS
# ======================

@usuarios_bp.route('/')
@admin_required
def listar_usuarios():
    """
    Lista todos los usuarios del sistema con gestión completa
    """
    # 🔧 SOLUCIÓN: Definir contexto con valores por defecto SIEMPRE
    context = {
        'usuarios': [],
        'oficinas': [],
        'aprobadores': [],
        'roles': [],
        'total_activos': 0,
        'total_inactivos': 0,
        'total_ldap': 0,
        'total_locales': 0,
        'total_usuarios': 0
    }
    
    try:
        conn = get_database_connection()
        cursor = conn.cursor()
        
        # Obtener todos los usuarios con información completa
        cursor.execute("""
            SELECT 
                u.UsuarioId,
                u.NombreUsuario,
                u.CorreoElectronico,
                u.Rol,
                u.OficinaId,
                o.NombreOficina,
                u.Activo,
                u.FechaCreacion,
                u.AprobadorId,
                a.NombreAprobador,
                CASE 
                    WHEN u.ContraseñaHash = 'LDAP_USER' THEN 'LDAP'
                    ELSE 'LOCAL'
                END as Tipo_Autenticacion
            FROM Usuarios u
            LEFT JOIN Oficinas o ON u.OficinaId = o.OficinaId
            LEFT JOIN Aprobadores a ON u.AprobadorId = a.AprobadorId
            ORDER BY u.Activo DESC, u.NombreUsuario
        """)
        
        usuarios = []
        for row in cursor.fetchall():
            usuarios.append({
                'id': row[0],
                'usuario': row[1],
                'email': row[2],
                'rol': row[3],
                'oficina_id': row[4],
                'oficina_nombre': row[5],
                'activo': bool(row[6]),
                'fecha_creacion': row[7],
                'aprobador_id': row[8],
                'aprobador_nombre': row[9],
                'tipo_auth': row[10]
            })
        
        # Obtener listas para formularios
        cursor.execute("SELECT OficinaId, NombreOficina FROM Oficinas WHERE Activo = 1 ORDER BY NombreOficina")
        oficinas = [{'id': row[0], 'nombre': row[1]} for row in cursor.fetchall()]
        
        cursor.execute("SELECT AprobadorId, NombreAprobador FROM Aprobadores WHERE Activo = 1 ORDER BY NombreAprobador")
        aprobadores = [{'id': row[0], 'nombre': row[1]} for row in cursor.fetchall()]
        
        # Roles disponibles según config/permissions.py
        roles_disponibles = [
            'administrador',
            'lider_inventario',
            'tesoreria',
            'aprobador',
            'oficina_coq',
            'oficina_polo_club',
            'oficina_cali',
            'oficina_pereira',
            'oficina_neiva',
            'oficina_kennedy',
            'oficina_bucaramanga',
            'oficina_nogal',
            'oficina_tunja',
            'oficina_cartagena',
            'oficina_morato',
            'oficina_medellin',
            'oficina_cedritos',
            'oficina_lourdes',
            'usuario'
        ]
        
        # Estadísticas
        cursor.execute("SELECT COUNT(*) FROM Usuarios WHERE Activo = 1")
        total_activos = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM Usuarios WHERE Activo = 0")
        total_inactivos = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM Usuarios WHERE ContraseñaHash = 'LDAP_USER'")
        total_ldap = cursor.fetchone()[0]
        
        # Calcular total de usuarios locales (no LDAP)
        total_locales = len(usuarios) - total_ldap
        
        conn.close()
        
        # ✅ Actualizar contexto con valores reales
        context.update({
            'usuarios': usuarios,
            'oficinas': oficinas,
            'aprobadores': aprobadores,
            'roles': roles_disponibles,
            'total_activos': total_activos,
            'total_inactivos': total_inactivos,
            'total_ldap': total_ldap,
            'total_locales': total_locales,
            'total_usuarios': len(usuarios)
        })
        
    except Exception as e:
        # ✅ CORRECCIÓN LÍNEA 220: Mensaje de error genérico sin detalles
        logger.error(f"Error en listado de usuarios", exc_info=False)
        flash('Error al listar usuarios. Por favor, intente nuevamente.', 'danger')
    
    # 🎯 SIEMPRE renderizar con el contexto completo (con valores por defecto si hubo error)
    return render_template('usuarios/listar.html', **context)

@usuarios_bp.route('/crear', methods=['GET', 'POST'])
@admin_required
def crear_usuario():
    """
    Crea un nuevo usuario (local o desde LDAP)
    """
    try:
        conn = get_database_connection()
        cursor = conn.cursor()
        
        if request.method == 'GET':
            # Obtener datos para formulario
            cursor.execute("SELECT OficinaId, NombreOficina FROM Oficinas WHERE Activo = 1 ORDER BY NombreOficina")
            oficinas = [{'id': row[0], 'nombre': row[1]} for row in cursor.fetchall()]
            
            cursor.execute("SELECT AprobadorId, NombreAprobador FROM Aprobadores WHERE Activo = 1 ORDER BY NombreAprobador")
            aprobadores = [{'id': row[0], 'nombre': row[1]} for row in cursor.fetchall()]
            
            # Roles disponibles
            roles_disponibles = [
                'administrador',
                'lider_inventario',
                'tesoreria',
                'aprobador',
                'oficina_coq',
                'oficina_polo_club',
                'usuario'
            ]
            
            conn.close()
            
            return render_template('usuarios/crear.html',
                                 oficinas=oficinas,
                                 aprobadores=aprobadores,
                                 roles=roles_disponibles)
        
        elif request.method == 'POST':
            tipo_usuario = request.form.get('tipo_usuario', 'local')
            
            if tipo_usuario == 'local':
                # Crear usuario local
                usuario_data = {
                    'usuario': request.form.get('nombre_usuario', '').strip(),
                    'nombre': request.form.get('nombre_completo', '').strip(),
                    'email': request.form.get('email', '').strip(),
                    'rol': request.form.get('rol', 'usuario'),
                    'password': request.form.get('password', ''),
                    'oficina_id': request.form.get('oficina_id'),
                    'aprobador_id': request.form.get('aprobador_id') or None,
                    'activo': 1 if request.form.get('activo') == 'on' else 0
                }
                
                # Validaciones
                if not usuario_data['usuario']:
                    flash('El nombre de usuario es obligatorio', 'danger')
                    return redirect(url_for('usuarios.crear_usuario'))
                
                if not usuario_data['password']:
                    flash('La contraseña es obligatoria para usuarios locales', 'danger')
                    return redirect(url_for('usuarios.crear_usuario'))
                
                # ✅ CORRECCIÓN: Sanitizar username para logs
                usuario_sanitizado = sanitizar_username(usuario_data['usuario'])
                
                # Verificar si el usuario ya existe
                cursor.execute("SELECT COUNT(*) FROM Usuarios WHERE NombreUsuario = ?", 
                              (usuario_data['usuario'],))
                if cursor.fetchone()[0] > 0:
                    # ✅ CORRECCIÓN LÍNEA 232: Log sanitizado
                    logger.warning(f"Intento de crear usuario existente: {usuario_sanitizado}")
                    flash('El nombre de usuario ya existe', 'danger')
                    conn.close()
                    return redirect(url_for('usuarios.crear_usuario'))
                
                # Crear usuario local
                success = UsuarioModel.crear_usuario_manual({
                    'usuario': usuario_data['usuario'],
                    'nombre': usuario_data['nombre'] or usuario_data['email'],
                    'rol': usuario_data['rol'],
                    'oficina_id': usuario_data['oficina_id'],
                    'password': usuario_data['password']
                })
                
                if success:
                    # Actualizar campos adicionales si es necesario
                    if usuario_data['aprobador_id'] or usuario_data['email']:
                        cursor.execute("""
                            UPDATE Usuarios 
                            SET AprobadorId = ?, 
                                CorreoElectronico = ?,
                                Activo = ?,
                                EsLDAP = 0
                            WHERE NombreUsuario = ?
                        """, (
                            usuario_data['aprobador_id'],
                            usuario_data['email'],
                            usuario_data['activo'],
                            usuario_data['usuario']
                        ))
                        conn.commit()
                    
                    # ✅ CORRECCIÓN LÍNEA 224: Log sanitizado
                    logger.info(f"Usuario local creado exitosamente: {usuario_sanitizado}")
                    flash('Usuario local creado exitosamente', 'success')
                    conn.close()
                    return redirect(url_for('usuarios.listar_usuarios'))
                else:
                    # ✅ CORRECCIÓN LÍNEA 232: Log sanitizado
                    logger.error(f"Error al crear usuario local: {usuario_sanitizado}")
                    flash('Error al crear el usuario local', 'danger')
                    conn.close()
                    return redirect(url_for('usuarios.crear_usuario'))
            
            elif tipo_usuario == 'ldap':
                # Crear usuario LDAP manualmente
                usuario_ldap = request.form.get('usuario_ldap', '').strip()
                email_ldap = request.form.get('email_ldap', '').strip()
                rol_ldap = request.form.get('rol_ldap', 'usuario')
                oficina_id_ldap = request.form.get('oficina_id_ldap')
                
                if not usuario_ldap:
                    flash('El nombre de usuario LDAP es obligatorio', 'danger')
                    return redirect(url_for('usuarios.crear_usuario'))
                
                # ✅ CORRECCIÓN: Sanitizar para logs
                usuario_ldap_sanitizado = sanitizar_username(usuario_ldap)
                
                # Verificar si ya existe
                cursor.execute("SELECT COUNT(*) FROM Usuarios WHERE NombreUsuario = ?", (usuario_ldap,))
                if cursor.fetchone()[0] > 0:
                    # ✅ CORRECCIÓN LÍNEA 263: Log sanitizado
                    logger.warning(f"Usuario LDAP ya existe en el sistema: {usuario_ldap_sanitizado}")
                    flash('El usuario LDAP ya existe en el sistema', 'warning')
                    conn.close()
                    return redirect(url_for('usuarios.crear_usuario'))
                
                # Crear usuario LDAP manual
                usuario_creado = UsuarioModel.crear_usuario_ldap_manual({
                    'usuario': usuario_ldap,
                    'email': email_ldap or f"{usuario_ldap}@qualitascolombia.com.co",
                    'rol': rol_ldap,
                    'oficina_id': oficina_id_ldap or 1
                })
                
                conn.close()
                
                if usuario_creado:
                    # ✅ CORRECCIÓN LÍNEA 267: Log sanitizado
                    logger.info(f"Usuario LDAP creado exitosamente: {usuario_ldap_sanitizado}")
                    flash(f'Usuario LDAP "{usuario_ldap}" creado exitosamente. Debe autenticarse primero con sus credenciales de dominio para activarse.', 'success')
                    return redirect(url_for('usuarios.listar_usuarios'))
                else:
                    # ✅ CORRECCIÓN LÍNEA 278: Log sanitizado
                    logger.error(f"Error al crear usuario LDAP: {usuario_ldap_sanitizado}")
                    flash('Error al crear el usuario LDAP', 'danger')
                    return redirect(url_for('usuarios.crear_usuario'))
            
            else:
                flash('Tipo de usuario no válido', 'danger')
                conn.close()
                return redirect(url_for('usuarios.crear_usuario'))
                
    except Exception as e:
        # ✅ CORRECCIÓN LÍNEA 285: Mensaje de error genérico
        logger.error("Error en creación de usuario", exc_info=False)
        flash('Error al crear usuario. Por favor, intente nuevamente.', 'danger')
        return redirect(url_for('usuarios.crear_usuario'))

@usuarios_bp.route('/editar/<int:usuario_id>', methods=['GET', 'POST'])
@admin_required
def editar_usuario(usuario_id):
    """
    Editar un usuario existente
    """
    try:
        conn = get_database_connection()
        cursor = conn.cursor()
        
        if request.method == 'GET':
            # Obtener datos del usuario
            cursor.execute("""
                SELECT 
                    u.UsuarioId,
                    u.NombreUsuario,
                    u.CorreoElectronico,
                    u.Rol,
                    u.OficinaId,
                    u.AprobadorId,
                    u.Activo,
                    CASE 
                        WHEN u.ContraseñaHash = 'LDAP_USER' THEN 'LDAP'
                        ELSE 'LOCAL'
                    END as Tipo_Autenticacion
                FROM Usuarios u
                WHERE u.UsuarioId = ?
            """, (usuario_id,))
            
            usuario = cursor.fetchone()
            
            if not usuario:
                flash('Usuario no encontrado', 'danger')
                conn.close()
                return redirect(url_for('usuarios.listar_usuarios'))
            
            # Obtener datos para formulario
            cursor.execute("SELECT OficinaId, NombreOficina FROM Oficinas WHERE Activo = 1 ORDER BY NombreOficina")
            oficinas = [{'id': row[0], 'nombre': row[1]} for row in cursor.fetchall()]
            
            cursor.execute("SELECT AprobadorId, NombreAprobador FROM Aprobadores WHERE Activo = 1 ORDER BY NombreAprobador")
            aprobadores = [{'id': row[0], 'nombre': row[1]} for row in cursor.fetchall()]
            
            # Roles disponibles
            roles_disponibles = [
                'administrador',
                'lider_inventario',
                'tesoreria',
                'aprobador',
                'oficina_coq',
                'oficina_polo_club',
                'usuario'
            ]
            
            conn.close()
            
            usuario_dict = {
                'id': usuario[0],
                'nombre_usuario': usuario[1],
                'email': usuario[2],
                'rol': usuario[3],
                'oficina_id': usuario[4],
                'aprobador_id': usuario[5],
                'activo': bool(usuario[6]),
                'tipo_auth': usuario[7]
            }
            
            return render_template('usuarios/editar.html',
                                 usuario=usuario_dict,
                                 oficinas=oficinas,
                                 aprobadores=aprobadores,
                                 roles=roles_disponibles)
        
        elif request.method == 'POST':
            # Actualizar usuario
            nuevo_rol = request.form.get('rol')
            nuevo_email = request.form.get('email', '').strip()
            nueva_oficina = request.form.get('oficina_id')
            nuevo_aprobador = request.form.get('aprobador_id') or None
            nuevo_activo = 1 if request.form.get('activo') == 'on' else 0
            
            # Obtener username para logs
            cursor.execute("SELECT NombreUsuario FROM Usuarios WHERE UsuarioId = ?", (usuario_id,))
            usuario_actual = cursor.fetchone()
            username_sanitizado = sanitizar_username(usuario_actual[0]) if usuario_actual else f"ID:{usuario_id}"
            
            # Verificar que no estamos desactivando el último administrador activo
            # CORRECCIÓN: Verificar ambos roles "admin" y "administrador"
            es_admin = (nuevo_rol in ['administrador', 'admin'])
            if nuevo_activo == 0 and es_admin:
                cursor.execute("""
                    SELECT COUNT(*) FROM Usuarios 
                    WHERE Rol IN ('administrador', 'admin') AND Activo = 1 AND UsuarioId != ?
                """, (usuario_id,))
                
                if cursor.fetchone()[0] == 0:
                    # ✅ CORRECCIÓN LÍNEA 299: Log sanitizado
                    logger.warning(f"Intento de desactivar último administrador: {username_sanitizado}")
                    flash('No se puede desactivar el último administrador activo', 'danger')
                    conn.close()
                    return redirect(url_for('usuarios.editar_usuario', usuario_id=usuario_id))
            
            # Actualizar usuario
            cursor.execute("""
                UPDATE Usuarios 
                SET Rol = ?,
                    CorreoElectronico = ?,
                    OficinaId = ?,
                    AprobadorId = ?,
                    Activo = ?
                WHERE UsuarioId = ?
            """, (
                nuevo_rol,
                nuevo_email,
                nueva_oficina,
                nuevo_aprobador,
                nuevo_activo,
                usuario_id
            ))
            
            conn.commit()
            conn.close()
            
            # ✅ CORRECCIÓN LÍNEA 302: Log sanitizado
            logger.info(f"Usuario actualizado exitosamente: {username_sanitizado} -> Rol:{nuevo_rol}")
            flash('Usuario actualizado exitosamente', 'success')
            return redirect(url_for('usuarios.listar_usuarios'))
            
    except Exception as e:
        # ✅ CORRECCIÓN LÍNEA 307: Mensaje de error genérico
        logger.error(f"Error en edición de usuario ID:{usuario_id}", exc_info=False)
        flash('Error al editar usuario. Por favor, intente nuevamente.', 'danger')
        return redirect(url_for('usuarios.listar_usuarios'))

@usuarios_bp.route('/cambiar-contrasena/<int:usuario_id>', methods=['POST'])
@admin_required
def cambiar_contrasena(usuario_id):
    """
    Cambiar contraseña de un usuario local (no LDAP)
    """
    try:
        nueva_contrasena = request.form.get('nueva_contrasena')
        confirmar_contrasena = request.form.get('confirmar_contrasena')
        
        if not nueva_contrasena:
            flash('La nueva contraseña es requerida', 'danger')
            return redirect(url_for('usuarios.editar_usuario', usuario_id=usuario_id))
        
        if nueva_contrasena != confirmar_contrasena:
            flash('Las contraseñas no coinciden', 'danger')
            return redirect(url_for('usuarios.editar_usuario', usuario_id=usuario_id))
        
        # Verificar que no sea usuario LDAP
        conn = get_database_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT ContraseñaHash FROM Usuarios WHERE UsuarioId = ?", (usuario_id,))
        resultado = cursor.fetchone()
        
        if resultado and resultado[0] == 'LDAP_USER':
            flash('No se puede cambiar contraseña a usuarios LDAP', 'danger')
            conn.close()
            return redirect(url_for('usuarios.editar_usuario', usuario_id=usuario_id))
        
        # Obtener username para logs
        cursor.execute("SELECT NombreUsuario FROM Usuarios WHERE UsuarioId = ?", (usuario_id,))
        usuario_actual = cursor.fetchone()
        username_sanitizado = sanitizar_username(usuario_actual[0]) if usuario_actual else f"ID:{usuario_id}"
        
        # Actualizar contraseña
        import bcrypt
        password_hash = bcrypt.hashpw(
            nueva_contrasena.encode('utf-8'), 
            bcrypt.gensalt()
        ).decode('utf-8')
        
        cursor.execute("""
            UPDATE Usuarios 
            SET ContraseñaHash = ?
            WHERE UsuarioId = ?
        """, (password_hash, usuario_id))
        
        conn.commit()
        conn.close()
        
        # ✅ CORRECCIÓN LÍNEA 348: Log sanitizado
        logger.info(f"Contraseña actualizada para usuario: {username_sanitizado}")
        flash('Contraseña actualizada exitosamente', 'success')
        return redirect(url_for('usuarios.listar_usuarios'))
        
    except Exception as e:
        # ✅ CORRECCIÓN: Mensaje de error genérico
        logger.error(f"Error cambiando contraseña para usuario ID:{usuario_id}", exc_info=False)
        flash('Error al cambiar contraseña. Por favor, intente nuevamente.', 'danger')
        return redirect(url_for('usuarios.editar_usuario', usuario_id=usuario_id))

@usuarios_bp.route('/desactivar/<int:usuario_id>', methods=['POST'])
@admin_required
def desactivar_usuario(usuario_id):
    """
    Desactivar usuario (eliminación lógica)
    """
    try:
        conn = get_database_connection()
        cursor = conn.cursor()
        
        # Obtener username para logs
        cursor.execute("SELECT NombreUsuario, Rol FROM Usuarios WHERE UsuarioId = ?", (usuario_id,))
        usuario = cursor.fetchone()
        username_sanitizado = sanitizar_username(usuario[0]) if usuario else f"ID:{usuario_id}"
        
        if usuario and usuario[1] in ['administrador', 'admin']:
            cursor.execute("""
                SELECT COUNT(*) FROM Usuarios 
                WHERE Rol IN ('administrador', 'admin') AND Activo = 1 AND UsuarioId != ?
            """, (usuario_id,))
            
            if cursor.fetchone()[0] == 0:
                # ✅ CORRECCIÓN LÍNEA 431: Log sanitizado
                logger.warning(f"Intento de desactivar último administrador activo: {username_sanitizado}")
                flash('No se puede desactivar el último administrador activo', 'danger')
                conn.close()
                return redirect(url_for('usuarios.listar_usuarios'))
        
        # Desactivar usuario
        cursor.execute("""
            UPDATE Usuarios 
            SET Activo = 0
            WHERE UsuarioId = ?
        """, (usuario_id,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Usuario desactivado: {username_sanitizado}")
        flash('Usuario desactivado exitosamente', 'success')
        return redirect(url_for('usuarios.listar_usuarios'))
        
    except Exception as e:
        logger.error(f"Error desactivando usuario ID:{usuario_id}", exc_info=False)
        flash('Error al desactivar usuario. Por favor, intente nuevamente.', 'danger')
        return redirect(url_for('usuarios.listar_usuarios'))

@usuarios_bp.route('/reactivar/<int:usuario_id>', methods=['POST'])
@admin_required
def reactivar_usuario(usuario_id):
    """
    Reactivar un usuario desactivado
    """
    try:
        conn = get_database_connection()
        cursor = conn.cursor()
        
        # Obtener username para logs
        cursor.execute("SELECT NombreUsuario FROM Usuarios WHERE UsuarioId = ?", (usuario_id,))
        usuario = cursor.fetchone()
        username_sanitizado = sanitizar_username(usuario[0]) if usuario else f"ID:{usuario_id}"
        
        cursor.execute("""
            UPDATE Usuarios 
            SET Activo = 1
            WHERE UsuarioId = ?
        """, (usuario_id,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Usuario reactivado: {username_sanitizado}")
        flash('Usuario reactivado exitosamente', 'success')
        return redirect(url_for('usuarios.listar_usuarios'))
        
    except Exception as e:
        logger.error(f"Error reactivando usuario ID:{usuario_id}", exc_info=False)
        flash('Error al reactivar usuario. Por favor, intente nuevamente.', 'danger')
        return redirect(url_for('usuarios.listar_usuarios'))

@usuarios_bp.route('/eliminar/<int:usuario_id>', methods=['POST'])
@admin_required
def eliminar_usuario(usuario_id):
    """
    Eliminar usuario permanentemente (solo si está desactivado)
    """
    try:
        conn = get_database_connection()
        cursor = conn.cursor()
        
        # Verificar que el usuario está desactivado
        cursor.execute("SELECT Activo, NombreUsuario, Rol FROM Usuarios WHERE UsuarioId = ?", (usuario_id,))
        usuario = cursor.fetchone()
        
        if usuario and usuario[0] == 1:
            flash('No se puede eliminar un usuario activo. Desactívelo primero.', 'danger')
            conn.close()
            return redirect(url_for('usuarios.listar_usuarios'))
        
        username_sanitizado = sanitizar_username(usuario[1]) if usuario else f"ID:{usuario_id}"
        
        # Verificar que no es el último admin (aunque esté desactivado)
        # CORRECCIÓN: Verificar ambos roles "admin" y "administrador"
        if usuario and usuario[2] in ['administrador', 'admin']:
            cursor.execute("""
                SELECT COUNT(*) FROM Usuarios 
                WHERE Rol IN ('administrador', 'admin') AND UsuarioId != ?
            """, (usuario_id,))
            
            if cursor.fetchone()[0] == 0:
                logger.warning(f"Intento de eliminar único administrador: {username_sanitizado}")
                flash('No se puede eliminar el único administrador del sistema', 'danger')
                conn.close()
                return redirect(url_for('usuarios.listar_usuarios'))
        
        # Eliminar usuario
        cursor.execute("DELETE FROM Usuarios WHERE UsuarioId = ?", (usuario_id,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Usuario eliminado permanentemente: {username_sanitizado}")
        flash('Usuario eliminado permanentemente', 'success')
        return redirect(url_for('usuarios.listar_usuarios'))
        
    except Exception as e:
        logger.error(f"Error eliminando usuario ID:{usuario_id}", exc_info=False)
        flash('Error al eliminar usuario. Por favor, intente nuevamente.', 'danger')
        return redirect(url_for('usuarios.listar_usuarios'))

@usuarios_bp.route('/buscar-ldap', methods=['POST'])
@admin_required
def buscar_usuario_ldap():
    """
    Buscar usuario en Active Directory
    """
    try:
        search_term = request.form.get('search_term', '').strip()
        
        if not search_term:
            return jsonify({'success': False, 'message': 'Término de búsqueda vacío'})
        
        # Verificar conexión LDAP
        if not Config.LDAP_ENABLED:  
            return jsonify({'success': False, 'message': 'LDAP deshabilitado'})
        
        from utils.ldap_auth import ad_auth
        
        # Buscar usuarios en AD
        usuarios_encontrados = ad_auth.search_user_by_name(search_term)
        
        # Formatear resultados
        resultados = []
        for usuario in usuarios_encontrados:
            resultados.append({
                'usuario': usuario.get('usuario', ''),
                'nombre': usuario.get('nombre', ''),
                'email': usuario.get('email', ''),
                'departamento': usuario.get('departamento', '')
            })
        
        return jsonify({
            'success': True,
            'usuarios': resultados,
            'total': len(resultados)
        })
        
    except Exception as e:
        # ✅ CORRECCIÓN: Mensaje de error genérico
        logger.error("Error en búsqueda LDAP", exc_info=False)
        return jsonify({'success': False, 'message': 'Error en la búsqueda de usuarios'})

@usuarios_bp.route('/sync-ldap/<string:username>', methods=['POST'])
@admin_required
def sincronizar_usuario_ldap(username):
    """
    Forzar sincronización de usuario desde LDAP
    """
    try:
        # Esta función requeriría que el admin ingrese la contraseña del usuario
        # o usar una cuenta de servicio con permisos de lectura
        flash('Función en desarrollo. Use /test-ldap para sincronizar usuarios.', 'info')
        return redirect(url_for('usuarios.listar_usuarios'))
        
    except Exception as e:
        # ✅ CORRECCIÓN: Log sanitizado
        username_sanitizado = sanitizar_username(username)
        logger.error(f"Error sincronizando usuario LDAP: {username_sanitizado}", exc_info=False)
        flash('Error sincronizando usuario', 'danger')
        return redirect(url_for('usuarios.listar_usuarios'))

# ======================
# API PARA INTERFAZ
# ======================

@usuarios_bp.route('/api/estadisticas')
@admin_required
def api_estadisticas():
    """
    Obtiene estadísticas de usuarios para dashboard
    """
    try:
        conn = get_database_connection()
        cursor = conn.cursor()
        
        # Total usuarios
        cursor.execute("SELECT COUNT(*) FROM Usuarios")
        total = cursor.fetchone()[0]
        
        # Usuarios activos
        cursor.execute("SELECT COUNT(*) FROM Usuarios WHERE Activo = 1")
        activos = cursor.fetchone()[0]
        
        # Usuarios LDAP
        cursor.execute("SELECT COUNT(*) FROM Usuarios WHERE ContraseñaHash = 'LDAP_USER'")
        ldap = cursor.fetchone()[0]
        
        # Distribución por rol
        cursor.execute("""
            SELECT Rol, COUNT(*) as cantidad
            FROM Usuarios 
            WHERE Activo = 1
            GROUP BY Rol
            ORDER BY cantidad DESC
        """)
        
        roles_dist = {}
        for row in cursor.fetchall():
            roles_dist[row[0]] = row[1]
        
        conn.close()
        
        return jsonify({
            'success': True,
            'estadisticas': {
                'total': total,
                'activos': activos,
                'inactivos': total - activos,
                'ldap': ldap,
                'local': total - ldap,
                'roles': roles_dist
            }
        })
        
    except Exception as e:
        # ✅ CORRECCIÓN: Mensaje de error genérico
        logger.error("Error obteniendo estadísticas de usuarios", exc_info=False)
        return jsonify({'success': False, 'message': 'Error al obtener estadísticas'})