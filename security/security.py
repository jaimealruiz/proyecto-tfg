import os
import jwt
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

# security/security.py
# Módulo de utilidades para firma y verificación JWT asimétrica (RS256) en A2A

# -----------------------------------------------------------------------------
# Función: sign_envelope
# Firma un Envelope (como dict) usando la clave privada RSA-2048.
# Parámetros:
#   - env:       El dict serializado del Envelope a firmar.
#   - issuer:    El agent logical name (e.g. "llm_agent" o "ventas_agent").
#   - audience:  El destinatario esperado (e.g. "broker").
# -----------------------------------------------------------------------------
def sign_envelope(env: Dict[str, Any], issuer: str, audience: str) -> str:
    private_key_path = os.getenv("PRIVATE_KEY_PATH")
    if not private_key_path:
        raise RuntimeError("VARIABLE DE ENTORNO PRIVATE_KEY_PATH no configurada")

    try:
        with open(private_key_path, "rb") as f:
            private_key = f.read()
    except FileNotFoundError:
        raise RuntimeError(f"Clave privada no encontrada en {private_key_path}")

    now = datetime.now(timezone.utc)
    payload = {
        "iss": issuer,
        "aud": audience,
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "env": env
    }
    # Generar JWT JWS con RS256
    token = jwt.encode(payload, private_key, algorithm="RS256")
    return token


# -----------------------------------------------------------------------------
# Función: verify_jwt_token
# Verifica un JWT recibido, valida la firma y devuelve el campo 'env'.
# -----------------------------------------------------------------------------
def verify_jwt_token(token: str) -> Dict[str, Any]:
    public_keys_dir = os.getenv("PUBLIC_KEYS_DIR")
    if not public_keys_dir:
        raise RuntimeError("VARIABLE DE ENTORNO PUBLIC_KEYS_DIR no configurada")

    # Extraer issuer sin verificar firma para localizar la clave pública
    unverified = jwt.decode(token, options={"verify_signature": False, "verify_aud": False})
    issuer = unverified.get("iss")
    if not issuer:
        raise RuntimeError("Token JWT sin claim 'iss'")

    # Buscar clave pública: primero <issuer>_public.pem, luego <issuer>.pub.pem
    candidates = [
        os.path.join(public_keys_dir, f"{issuer}_public.pem"),
        os.path.join(public_keys_dir, f"{issuer}.pub.pem"),
        os.path.join(public_keys_dir, f"{issuer}.pem")
    ]
    pub_path = next((p for p in candidates if os.path.isfile(p)), None)
    if not pub_path:
        raise RuntimeError(f"Clave pública no encontrada para issuer '{issuer}' en {public_keys_dir}")

    with open(pub_path, "rb") as f:
        public_key = f.read()

    # Validación completa: firma, exp y aud (si se desea)
    decoded = jwt.decode(token, public_key, audience=os.getenv("BROKER_ID"), algorithms=["RS256"])
    env = decoded.get("env")
    if env is None:
        raise RuntimeError("Token JWT sin claim 'env'")
    return env
