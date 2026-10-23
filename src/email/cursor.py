from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Cursor:
    history_id: str
    ultima_leitura: datetime


def ler_cursor(caminho: Path) -> Cursor | None:
    if not caminho.exists():
        return None
    bruto = json.loads(caminho.read_text(encoding="utf-8"))
    return Cursor(str(bruto["history_id"]), datetime.fromisoformat(bruto["ultima_leitura"]))


def gravar_cursor(caminho: Path, cursor: Cursor) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    conteudo = {
        "history_id": cursor.history_id,
        "ultima_leitura": cursor.ultima_leitura.isoformat(),
    }
    temporario.write_text(json.dumps(conteudo), encoding="utf-8")
    os.chmod(temporario, 0o600)
    temporario.replace(caminho)
