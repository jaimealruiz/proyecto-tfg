# security.py

import os
import jwt
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

# Variables de entorno:
#   PRIVATE_KEY_PATH → ruta a la clave RSA privada PEM
#   PUBLIC_KEYS_DIR → carpeta donde hay .pem de forma {agent_id}.pub.pem
PRIVATE_KEY_PATH = os.getenv("PRIVATE_KEY_PATH", "/secrets/private.pem")
PUBLIC_KEYS_DIR   = os.getenv("PUBLIC_KEYS_DIR",   "/secrets/public/")

# Carga global de la clave privada
with open(PRIVATE_KEY_PATH, "rb") as f:
    _PRIVATE_KEY = f.read()

def sign_envelope(env: Dict[str, Any], issuer: str, audience: str) -> str:
    """
    Crea un JWT JWS con el contenido completo de 'env' en el claim 'env'.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "iss": issuer,
        "aud": audience,
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "env": env
    }
    token = jwt.encode(payload, _PRIVATE_KEY, algorithm="RS256")
    return token

def verify_jwt_token(token: str) -> Dict[str, Any]:
    """
    Valida la firma y claims de un JWT recibido; devuelve el claim 'env'.
    """
    unverified = jwt.decode(token, options={"verify_signature": False})
    issuer = unverified["iss"]
    pub_path = os.path.join(PUBLIC_KEYS_DIR, f"{issuer}.pub.pem")
    with open(pub_path, "rb") as f:
        pub = f.read()
    decoded = jwt.decode(token, pub, audience=None, algorithms=["RS256"])
    # `decoded["env"]` es el Envelope original
    return decoded["env"]
