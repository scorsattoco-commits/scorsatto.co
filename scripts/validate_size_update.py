"""Fail closed if a supplier run changed anything beyond stock metadata."""

import json
import re
import sys
from pathlib import Path


ALLOWED_FIELDS = {"sizes", "stock", "lastCheckedAt"}


def products_from_html(path):
    html = Path(path).read_text(encoding="utf-8")
    match = re.search(r"const\s+PRODUCTS\s*=\s*(\[.*?\]);\s*const\s+CATEGORIES\s*=", html, re.S)
    if not match:
        raise RuntimeError(f"Não encontrei PRODUCTS em {path}")
    return json.loads(match.group(1))


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Uso: validate_size_update.py <index-base.html> <index-atual.html>")

    before = products_from_html(sys.argv[1])
    after = products_from_html(sys.argv[2])
    if [item.get("id") for item in before] != [item.get("id") for item in after]:
        raise SystemExit("Bloqueado: a lista ou a ordem de produtos foi alterada.")

    violations = []
    for old, new in zip(before, after):
        changed = {key for key in set(old) | set(new) if old.get(key) != new.get(key)}
        forbidden = changed - ALLOWED_FIELDS
        if forbidden:
            violations.append({"id": old.get("id"), "fields": sorted(forbidden)})

    if violations:
        raise SystemExit("Bloqueado: alterações fora de sizes, stock e lastCheckedAt: " + json.dumps(violations, ensure_ascii=False))

    print("Validação aprovada: somente tamanhos, estoque e data de conferência foram alterados.")


if __name__ == "__main__":
    main()
