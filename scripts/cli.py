#!/usr/bin/env python3
"""
scripts/cli.py

Cliente de línea de comandos para enviar preguntas al LLM-Agent
y mostrar en consola el SQL generado y la respuesta.
"""

import os
import sys
import argparse
import requests
import textwrap

def main():
    parser = argparse.ArgumentParser(
        description="Enviar una pregunta en lenguaje natural al LLM-Agent"
    )
    parser.add_argument(
        "pregunta",
        nargs="+",
        help="Pregunta en lenguaje natural que será traducida a SQL y ejecutada"
    )
    parser.add_argument(
        "--url",
        default=os.getenv("LLM_AGENT_URL", "http://localhost:8003"),
        help="URL base del LLM-Agent (p.ej. http://llm-agent:8003)"
    )
    args = parser.parse_args()

    q = " ".join(args.pregunta).strip()
    endpoint = f"{args.url.rstrip('/')}/query"
    payload = {"pregunta": q}

    try:
        resp = requests.post(endpoint, json=payload, timeout=200)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"❌ Error conectando al LLM-Agent: {e}", file=sys.stderr)
        sys.exit(1)

    data = resp.json()
    # Si devuelve directamente sql+respuesta, mostramos
    sql = data.get("sql")
    respuesta = data.get("respuesta") or data.get("error") or data.get("detail")

    if sql:
        print("\n--- SQL generado ---")
        print(sql)
    if respuesta is not None:
        print("\n--- Respuesta LLM ---")
        # respetar saltos, etc.
        print(textwrap.indent(respuesta, "  "))
    else:
        print("\n⚠️  No se obtuvo campo `respuesta` en la respuesta JSON.")

if __name__ == "__main__":
    main()
