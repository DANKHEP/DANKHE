"""Uso: python -m sm 830.123/2010"""

import json
import sys

from .service import verificar_status_processo

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: python -m sm <processo>   (ex.: python -m sm 830.123/2010)")
    try:
        print(json.dumps(verificar_status_processo(sys.argv[1]), ensure_ascii=False, indent=2))
    except Exception as exc:  # noqa: BLE001 - mensagem amigável na linha de comando
        sys.exit(f"Erro: {exc}")
