from __future__ import annotations

import plistlib
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from src.agendamento import executor as modulo_executor
from src.agendamento.configuracao import Agendamento, Rotina, agendamento_do_config
from src.agendamento.executor import EstouroDeTempo, executar
from src.agendamento.plist import gerar_plist
from src.config import carregar

RAIZ_FALSA = Path("/raiz/falsa")


def agendamento(retry: bool = True) -> Agendamento:
    return Agendamento(
        rotulo="teste.rotinas",
        tolerancia_min=10,
        timeout_min=20,
        interpretador="venv/py",
        retry_ao_acordar=retry,
        rotinas=(
            Rotina("resumo", ("make", "resumo"), horario="07:45"),
            Rotina("descoberta", ("make", "descoberta"), horario="06:30"),
            Rotina("email", ("make", "email"), intervalo_min=30),
        ),
    )


class Corredor:
    def __init__(self, codigo: int = 0):
        self.chamadas: list[str] = []
        self.codigo = codigo

    def __call__(self, rotina: Rotina) -> int:
        self.chamadas.append(rotina.nome)
        return self.codigo


def dia(hora: int, minuto: int, dias: int = 0) -> datetime:
    return datetime(2030, 1, 10, hora, minuto) + timedelta(days=dias)


def test_plist_tem_uma_janela_por_horario_e_o_intervalo_do_config():
    cfg = agendamento_do_config()
    dados = plistlib.loads(gerar_plist(cfg, RAIZ_FALSA, RAIZ_FALSA / "log"))
    limites = carregar("limites")
    horarios = limites["horarios"]
    hora, minuto = (int(p) for p in horarios["resumo_diario"].split(":"))
    assert dados["Label"] == limites["agendamento"]["rotulo"]
    assert {"Hour": hora, "Minute": minuto} in dados["StartCalendarInterval"]
    assert dados["StartInterval"] == horarios["email_intervalo_min"] * 60
    assert dados["RunAtLoad"] is True
    assert dados["WorkingDirectory"] == str(RAIZ_FALSA)
    assert dados["ProgramArguments"][-1] == "src.agendamento.executor"


def test_plist_usa_o_horario_que_o_config_der():
    dados = plistlib.loads(gerar_plist(agendamento(), RAIZ_FALSA, RAIZ_FALSA / "log"))
    assert dados["Label"] == "teste.rotinas"
    assert dados["StartCalendarInterval"] == [
        {"Hour": 6, "Minute": 30},
        {"Hour": 7, "Minute": 45},
    ]
    assert dados["StartInterval"] == 1800


def test_janela_no_horario_roda_uma_vez_e_registra(tmp_path):
    corredor = Corredor()
    registro = tmp_path / "execucoes.json"
    executar(agendamento(), registro, dia(7, 46), corredor)
    assert corredor.chamadas.count("resumo") == 1
    assert '"resumo"' in registro.read_text(encoding="utf-8")


def test_janela_ja_executada_nao_repete(tmp_path):
    corredor = Corredor()
    registro = tmp_path / "execucoes.json"
    executar(agendamento(), registro, dia(7, 46), corredor)
    executar(agendamento(), registro, dia(9, 0), corredor)
    assert corredor.chamadas.count("resumo") == 1


def test_janela_perdida_com_retry_roda_uma_vez_ao_acordar_e_registra(tmp_path):
    corredor = Corredor()
    registro = tmp_path / "execucoes.json"
    executar(agendamento(retry=True), registro, dia(11, 0), corredor)
    executar(agendamento(retry=True), registro, dia(11, 5), corredor)
    assert corredor.chamadas.count("resumo") == 1
    assert '"recuperada": true' in registro.read_text(encoding="utf-8")


def test_janela_perdida_sem_retry_nao_roda_e_registra_a_perda(tmp_path):
    corredor = Corredor()
    registro = tmp_path / "execucoes.json"
    executar(agendamento(retry=False), registro, dia(11, 0), corredor)
    executar(agendamento(retry=False), registro, dia(11, 5), corredor)
    assert "resumo" not in corredor.chamadas
    assert registro.read_text(encoding="utf-8").count("perdida") == 2


def test_antes_do_horario_de_hoje_a_janela_de_ontem_perdida_e_recuperada(tmp_path):
    corredor = Corredor()
    executar(agendamento(), tmp_path / "e.json", dia(6, 0), corredor)
    assert corredor.chamadas.count("resumo") == 1


def test_rotina_por_intervalo_so_roda_quando_o_intervalo_passou(tmp_path):
    corredor = Corredor()
    registro = tmp_path / "e.json"
    executar(agendamento(), registro, dia(8, 0), corredor)
    executar(agendamento(), registro, dia(8, 10), corredor)
    executar(agendamento(), registro, dia(8, 31), corredor)
    assert corredor.chamadas.count("email") == 2


def test_falha_da_rotina_fica_registrada(tmp_path):
    registro = tmp_path / "e.json"
    executar(agendamento(), registro, dia(7, 46), Corredor(codigo=2))
    assert "falha" in registro.read_text(encoding="utf-8")


def test_plist_usa_o_interpretador_do_config():
    dados = plistlib.loads(gerar_plist(agendamento(), RAIZ_FALSA, RAIZ_FALSA / "log"))
    assert dados["ProgramArguments"][0] == str(RAIZ_FALSA / "venv/py")


def test_estouro_de_tempo_registra_timeout_e_segue_para_a_proxima_rotina(tmp_path):
    chamadas = []

    def corredor(rotina):
        chamadas.append(rotina.nome)
        if rotina.nome == "descoberta":
            raise EstouroDeTempo
        return 0

    registro = tmp_path / "e.json"
    executar(agendamento(), registro, dia(7, 46), corredor)
    texto = registro.read_text(encoding="utf-8")
    assert "timeout" in texto
    assert "resumo" in chamadas and "email" in chamadas


def test_correr_comando_converte_timeout_do_subprocess(monkeypatch):
    def falso(*args, **kwargs):
        assert kwargs["timeout"] == 120
        raise subprocess.TimeoutExpired("x", 120)

    monkeypatch.setattr(modulo_executor.subprocess, "run", falso)
    try:
        modulo_executor.correr_comando(Rotina("r", ("x",)), 2)
    except EstouroDeTempo:
        return
    raise AssertionError


def test_excecao_na_segunda_rotina_nao_perde_o_registro_da_primeira(tmp_path):
    registro = tmp_path / "e.json"

    def corredor(rotina):
        if rotina.nome == "descoberta":
            raise RuntimeError
        return 0

    try:
        executar(agendamento(), registro, dia(7, 46), corredor)
    except RuntimeError:
        pass
    assert '"resumo"' in registro.read_text(encoding="utf-8")
    assert not list(tmp_path.glob("*.tmp"))
