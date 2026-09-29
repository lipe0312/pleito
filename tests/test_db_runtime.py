from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.db.auditoria import registrar_auditoria
from src.db.conexao import ConfiguracaoBancoInvalida, validar_destino
from src.db.flags import ler_flag


def test_leitura_de_flag_parametriza_chave_com_conteudo_hostil():
    chave = "sistema_ativo' OR true; DROP TABLE vaga; --"
    with patch("src.db.flags.conectar") as conectar:
        conexao = conectar.return_value.__enter__.return_value
        cursor = conexao.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (False,)
        assert ler_flag(chave) is False
    consulta, parametros = cursor.execute.call_args.args
    assert "chave = %s" in consulta
    assert parametros == (chave,)


def test_auditoria_parametriza_campos_e_json():
    valores = ("ator'); DELETE FROM auditoria; --", "acao", "vaga", "1")
    conexao = MagicMock()
    registrar_auditoria(
        conexao,
        ator=valores[0],
        acao=valores[1],
        entidade=valores[2],
        entidade_id=valores[3],
        depois={"texto": "'); DROP TABLE vaga; --"},
    )
    cursor = conexao.cursor.return_value.__enter__.return_value
    consulta, parametros = cursor.execute.call_args.args
    assert "VALUES (%s, %s, %s, %s, %s, %s)" in consulta
    assert parametros[:4] == valores
    assert "DROP TABLE" not in consulta


def test_destino_recusa_cluster_na_porta_da_disciplina():
    with pytest.raises(ConfiguracaoBancoInvalida):
        validar_destino("127.0.0.1", 5432, "pleito")


def test_destino_recusa_banco_diferente():
    with pytest.raises(ConfiguracaoBancoInvalida):
        validar_destino("127.0.0.1", 55432, "MATA_60_2026_2")


def test_rotacao_nao_passa_senha_por_argumento_de_processo():
    script = Path("scripts/rotacionar-senha.sh").read_text(encoding="utf-8")
    assert 'python3 - "$role" "$nova"' not in script
    assert 'python3 - "$chave" "$nova"' not in script
    assert "printf '%s\\n' \"$nova\" | python3" in script
