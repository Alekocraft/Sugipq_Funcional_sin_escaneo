# generar_hash.py
import bcrypt
import logging
logger = logging.getLogger(__name__)

usuarios = {
    "aprobador": "123456",
}
logger.info("🔐 HASHES REALES PARA SQL SERVER\n" + "="*50)

for user, pwd in usuarios.items():
    hash_real = bcrypt.hashpw(pwd.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    logger.info(f"Usuario: {user}")

    logger.info(f"Contraseña: {pwd}")

    logger.info(f"Hash: {hash_real}\n")

# Esto mantiene la ventana abierta hasta que pulses Enter
input("✅ Presiona Enter para salir...")