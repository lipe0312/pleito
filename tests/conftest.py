from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from viabilidade.contratos import Funcao, ModeloTrabalho, Senioridade, VagaBruta


@pytest.fixture
def vaga_completa() -> VagaBruta:
    return VagaBruta(
        fonte="greenhouse",
        id_externo="123",
        url="https://boards.greenhouse.io/nubank/jobs/123",
        titulo="Software Engineer Intern",
        empresa="nubank",
        descricao="x" * 400,
        local="Sao Paulo, Brazil",
        pais="BR",
        senioridade=Senioridade.ESTAGIO,
        modelo=ModeloTrabalho.REMOTO,
        funcao=Funcao.ENGENHARIA,
        anos_experiencia=1,
    )


@pytest.fixture
def fixtures() -> Path:
    return Path(__file__).resolve().parent / "fixtures"
