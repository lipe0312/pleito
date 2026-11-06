from __future__ import annotations

import re
from html import escape

PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def renderizar(modelo: str, **valores: object) -> str:
    return PLACEHOLDER.sub(lambda achado: escape(str(valores[achado.group(1)]), quote=True), modelo)
