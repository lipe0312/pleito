from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.config import carregar
from src.repositorio_guarda.guarda import (
    caminho_proibido,
    compilar,
    normalizar,
    procurar_atribuicao,
    procurar_segredos,
)

RAIZ = Path(__file__).resolve().parent.parent


def montar(*partes: str) -> str:
    return "".join(partes)


def chave_openai() -> str:
    return montar("sk", "-", "proj", "-", "A1b2C3d4E5f6G7h8I9j0K1l2M3")


def token_github() -> str:
    return montar("gh", "p_", "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8")


def cabecalho_pem() -> str:
    return montar("-----", "BEGIN RSA PRIVATE", " KEY", "-----")


def ambiente_sem_git() -> dict[str, str]:
    base = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    base["PYTHONPATH"] = str(RAIZ)
    base["GIT_CONFIG_GLOBAL"] = os.devnull
    base["GIT_CONFIG_SYSTEM"] = os.devnull
    return base


def git(repo: Path, *argumentos: str) -> None:
    subprocess.run(
        ["git", *argumentos],
        cwd=repo,
        env=ambiente_sem_git(),
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q")
    return tmp_path


def escrever(repo: Path, caminho: str, conteudo: str = "x\n") -> None:
    destino = repo / caminho
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(conteudo, encoding="utf-8")


def preparar(repo: Path, *caminhos: str) -> None:
    git(repo, "add", "-f", *caminhos)


def guarda(repo: Path, *argumentos: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "src.repositorio_guarda", *argumentos],
        cwd=repo,
        env=ambiente_sem_git(),
        capture_output=True,
        text=True,
    )


@pytest.fixture(scope="module")
def regras() -> dict:
    return carregar("repositorio")


@pytest.mark.parametrize(
    "caminho",
    [
        "dados/curriculo.yaml",
        "segredos/gmail.json",
        ".env",
        ".env.local",
        "app/.env",
        "Dados/curriculo.yaml",
        "SEGREDOS/token.txt",
        ".ENV",
        "./dados/x",
        "src/../dados/x",
        "../fora/x",
        "segredos/perfil_navegador/Default/Cookies",
        "perfil_navegador/Default/Cookies",
        "x/gupy_perfil_navegador/Default/Cookies",
        "src/dados/x.yaml",
        "docs/segredos/x.md",
        "a/b/c/Dados/x",
        "a/SEGREDOS",
        "\u017fegredos/x",
        "src/da\u017fdos/../dados/x",
    ],
)
def test_caminho_proibido_recusa(regras, caminho):
    assert caminho_proibido(caminho, regras["caminhos"])


@pytest.mark.parametrize(
    "caminho",
    [
        ".env.example",
        "src/painel/app.py",
        "docs/dados.md",
        "tests/fixtures/guia_ficticio.md",
        "src/dados_x/a.py",
        "segredos_x/a",
        "src/meus_dados/a.py",
    ],
)
def test_caminho_proibido_aceita(regras, caminho):
    assert not caminho_proibido(caminho, regras["caminhos"])


def test_arquivo_staged_em_dados_e_recusado(repo):
    escrever(repo, "dados/curriculo.yaml")
    preparar(repo, "dados/curriculo.yaml")
    resultado = guarda(repo, "arquivos")
    assert resultado.returncode == 1
    assert "dados/curriculo.yaml" in resultado.stderr


def test_arquivo_staged_em_segredos_e_recusado(repo):
    escrever(repo, "segredos/token.json")
    preparar(repo, "segredos/token.json")
    resultado = guarda(repo, "arquivos")
    assert resultado.returncode == 1
    assert "segredos/token.json" in resultado.stderr


def test_env_staged_e_recusado_e_exemplo_passa(repo):
    escrever(repo, ".env")
    escrever(repo, ".env.example")
    preparar(repo, ".env")
    assert guarda(repo, "arquivos").returncode == 1
    git(repo, "reset", "-q")
    preparar(repo, ".env.example")
    assert guarda(repo, "arquivos").returncode == 0


def test_pasta_com_maiuscula_staged_e_recusada(repo):
    escrever(repo, "Dados/x.yaml")
    preparar(repo, "Dados/x.yaml")
    resultado = guarda(repo, "arquivos")
    assert resultado.returncode == 1
    assert "Dados/x.yaml" in resultado.stderr


def test_perfil_de_navegador_staged_e_recusado(repo):
    escrever(repo, "gupy_perfil_navegador/Default/Cookies")
    preparar(repo, "gupy_perfil_navegador/Default/Cookies")
    assert guarda(repo, "arquivos").returncode == 1


def test_symlink_staged_e_recusado_mesmo_para_alvo_permitido(repo):
    escrever(repo, "docs/ok.md")
    (repo / "atalho.md").symlink_to("docs/ok.md")
    preparar(repo, "atalho.md")
    resultado = guarda(repo, "arquivos")
    assert resultado.returncode == 1
    assert "atalho.md" in resultado.stderr


def test_symlink_chamado_dados_staged_e_recusado(repo, tmp_path_factory):
    alvo = tmp_path_factory.mktemp("alvo")
    (repo / "dados").symlink_to(alvo)
    preparar(repo, "dados")
    assert guarda(repo, "arquivos").returncode == 1


def test_symlink_nao_staged_nao_bloqueia(repo, tmp_path_factory):
    alvo = tmp_path_factory.mktemp("alvo")
    (repo / "dados").symlink_to(alvo)
    (repo / ".env").symlink_to(alvo / "env")
    escrever(repo, "src/a.py")
    preparar(repo, "src/a.py")
    assert guarda(repo, "arquivos").returncode == 0


def test_remover_do_indice_arquivo_de_dados_nao_bloqueia(repo):
    escrever(repo, "dados/x.yaml")
    preparar(repo, "dados/x.yaml")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "base")
    git(repo, "rm", "-q", "--cached", "dados/x.yaml")
    assert guarda(repo, "arquivos").returncode == 0


def test_arquivo_comum_passa(repo):
    escrever(repo, "src/a.py", "x = 1\n")
    preparar(repo, "src/a.py")
    assert guarda(repo, "arquivos").returncode == 0


@pytest.mark.parametrize(
    "linha",
    [
        lambda: f"OPENAI = '{chave_openai()}'",
        lambda: f"token: {token_github()}",
        lambda: cabecalho_pem(),
        lambda: montar('{"client', '_secret": "', "GOCSPX", '-abcdefgh1234"}'),
        lambda: montar("client", "_secret = '", "abcdefgh12345678", "'"),
        lambda: montar("client", "_secret: ", "abcdefgh12345678abcd"),
        lambda: montar('"refresh', '_token": "', "1//0gAbCdEfGhIjKl", '"'),
        lambda: montar("refresh", "_token=", "1//0gAbCdEfGhIjKlMnOp"),
        lambda: montar("github", "_pat_", "11ABCDEFG0abcdefghijklmn_opqrstuv"),
    ],
)
def test_procurar_segredos_acha_cada_padrao(regras, linha):
    assert procurar_segredos(["ok", linha(), "fim"], regras["segredos"])


@pytest.mark.parametrize(
    "linha",
    [
        "cliente = ambiente.client_secret",
        "def refresh_token(self):",
        "refresh_token = ler_do_keychain()",
        "sk-curto",
        "chave = os.getenv('CLIENT_SECRET')",
    ],
)
def test_procurar_segredos_ignora_codigo_comum(regras, linha):
    assert not procurar_segredos([linha], regras["segredos"])


def test_segredo_no_meio_de_diff_grande_e_recusado(repo):
    corpo = [f"linha_{i} = {i}" for i in range(400)]
    corpo.insert(217, f"CHAVE = '{chave_openai()}'")
    escrever(repo, "src/grande.py", "\n".join(corpo) + "\n")
    escrever(repo, "src/limpo.py", "y = 2\n")
    preparar(repo, "src/limpo.py", "src/grande.py")
    resultado = guarda(repo, "diff")
    assert resultado.returncode == 1
    assert "src/grande.py:218" in resultado.stderr
    assert "chave_openai" in resultado.stderr
    assert chave_openai() not in resultado.stderr


def test_diff_sem_segredo_passa(repo):
    escrever(repo, "src/a.py", "x = 1\nsk = 'curto'\n")
    preparar(repo, "src/a.py")
    assert guarda(repo, "diff").returncode == 0


def test_segredo_apenas_removido_nao_bloqueia(repo):
    escrever(repo, "src/a.py", f"CHAVE = '{chave_openai()}'\n")
    preparar(repo, "src/a.py")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "base")
    escrever(repo, "src/a.py", "CHAVE = ''\n")
    preparar(repo, "src/a.py")
    assert guarda(repo, "diff").returncode == 0


def test_pem_staged_e_recusado(repo):
    escrever(repo, "docs/nota.txt", f"{cabecalho_pem()}\nabc\n")
    preparar(repo, "docs/nota.txt")
    assert guarda(repo, "diff").returncode == 1


@pytest.mark.parametrize(
    "mensagem",
    [
        "Co-Authored-By: Alguem <a@b.c>",
        "co-authored-by: Alguem <a@b.c>",
        "CO-AUTHORED-BY: Alguem",
        "  Co-authored-by: Alguem",
        "Generated with [Tool](https://x.y)",
        "generated WITH uma ferramenta",
        "Generated by uma ferramenta",
        "Created by: Claude",
        "noreply@" + "anthropic" + ".com",
        "Feito com Claude Code",
        "\U0001F916 gerado",
    ],
)
def test_atribuicao_e_encontrada(regras, mensagem):
    assert procurar_atribuicao(["Corrigir parser", "", mensagem], regras["atribuicao"])


@pytest.mark.parametrize(
    "mensagem",
    [
        "Corrigir parser de robots",
        "Barrar segredo e dado pessoal no commit",
        "Registrar autor do evento de email",
    ],
)
def test_mensagem_limpa_passa(regras, mensagem):
    assert not procurar_atribuicao([mensagem, "", "Corpo tecnico."], regras["atribuicao"])


def test_linhas_de_comentario_do_git_sao_ignoradas(repo):
    mensagem = repo / "COMMIT_EDITMSG"
    mensagem.write_text("Corrigir parser\n\n# Co-Authored-By: exemplo do git\n", encoding="utf-8")
    assert guarda(repo, "mensagem", str(mensagem)).returncode == 0


def test_commit_msg_recusa_atribuicao_pela_cli(repo):
    mensagem = repo / "COMMIT_EDITMSG"
    mensagem.write_text("Corrigir parser\n\nCo-Authored-By: Alguem <a@b.c>\n", encoding="utf-8")
    resultado = guarda(repo, "mensagem", str(mensagem))
    assert resultado.returncode == 1
    assert "co_authored_by" in resultado.stderr


def test_commit_msg_aceita_mensagem_tecnica_pela_cli(repo):
    mensagem = repo / "COMMIT_EDITMSG"
    mensagem.write_text("Corrigir parser\n\nPorque o robots falhava.\n", encoding="utf-8")
    assert guarda(repo, "mensagem", str(mensagem)).returncode == 0


def test_normalizar_une_composto_e_decomposto():
    assert normalizar("cafe\u0301/x") == normalizar("caf\u00e9/x")


def test_normalizar_aplica_casefold():
    assert normalizar("\u017fegredos/X") == "segredos/x"


def test_submodulo_staged_e_recusado(repo):
    git(
        repo,
        "update-index",
        "--add",
        "--cacheinfo",
        "160000,1111111111111111111111111111111111111111,vendor/sub",
    )
    resultado = guarda(repo, "arquivos")
    assert resultado.returncode == 1
    assert "vendor/sub" in resultado.stderr
    assert "submodulo" in resultado.stderr


def test_linha_adicionada_que_imita_cabecalho_de_diff_e_varrida(repo):
    escrever(repo, "src/a.py", f"x = 1\n++ {chave_openai()}\n")
    preparar(repo, "src/a.py")
    resultado = guarda(repo, "diff")
    assert resultado.returncode == 1
    assert "src/a.py:2" in resultado.stderr


def test_linha_adicionada_que_imita_cabecalho_de_arquivo_novo_e_varrida(repo):
    escrever(repo, "src/a.py", f"++ b/src/outro.py\n{chave_openai()}\n")
    preparar(repo, "src/a.py")
    resultado = guarda(repo, "diff")
    assert resultado.returncode == 1
    assert "src/a.py:2" in resultado.stderr


@pytest.mark.parametrize(
    "separador",
    ["\u2028", "\u2029", "\u0085", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e", "\r"],
)
def test_segredo_depois_de_separador_unicode_e_varrido(repo, separador):
    escrever(repo, "src/a.py", f"x = 1{separador}CHAVE = '{chave_openai()}'\n")
    preparar(repo, "src/a.py")
    assert guarda(repo, "diff").returncode == 1


def test_arquivo_com_fim_de_linha_windows_e_varrido(repo):
    destino = repo / "src/a.py"
    destino.parent.mkdir()
    destino.write_bytes(f"x = 1\r\nCHAVE = '{chave_openai()}'\r\n".encode())
    preparar(repo, "src/a.py")
    resultado = guarda(repo, "diff")
    assert resultado.returncode == 1
    assert "src/a.py:2" in resultado.stderr


def test_segredo_em_arquivo_binario_e_varrido(repo):
    destino = repo / "src/blob.bin"
    destino.parent.mkdir()
    destino.write_bytes(b"\x00\x01\x02\n" + f"CHAVE = '{chave_openai()}'\n".encode() + b"\x00")
    preparar(repo, "src/blob.bin")
    assert guarda(repo, "diff").returncode == 1


def test_segredo_em_arquivo_com_diff_desligado_no_gitattributes_e_varrido(repo):
    escrever(repo, ".gitattributes", "*.txt -diff\n")
    escrever(repo, "docs/nota.txt", f"CHAVE = '{chave_openai()}'\n")
    preparar(repo, ".gitattributes", "docs/nota.txt")
    assert guarda(repo, "diff").returncode == 1


def test_segredo_em_arquivo_com_driver_de_diff_externo_e_varrido(repo):
    escrever(repo, ".gitattributes", "*.txt diff=falso\n")
    escrever(repo, "docs/nota.txt", f"CHAVE = '{chave_openai()}'\n")
    git(repo, "config", "diff.falso.textconv", "false")
    preparar(repo, ".gitattributes", "docs/nota.txt")
    assert guarda(repo, "diff").returncode == 1


def test_atribuicao_depois_de_separador_unicode_na_mensagem(repo):
    mensagem = repo / "COMMIT_EDITMSG"
    mensagem.write_text("Corrigir parser\u2028Co-Authored-By: X <a@b.c>\n", encoding="utf-8")
    assert guarda(repo, "mensagem", str(mensagem)).returncode == 1


def test_atribuicao_com_fim_de_linha_windows_na_mensagem(repo):
    mensagem = repo / "COMMIT_EDITMSG"
    mensagem.write_bytes(b"Corrigir parser\r\n\r\nCo-Authored-By: X <a@b.c>\r\n")
    assert guarda(repo, "mensagem", str(mensagem)).returncode == 1


@pytest.mark.parametrize(
    "linha",
    [
        lambda: montar("AK", "IA", "IOSFODNN7EXAMPLE"),
        lambda: montar("GOC", "SPX", "-abcdefghijklmnopqrstuvwx"),
        lambda: montar("ya", "29.", "a0AbCdEfGhIjKlMnOpQrStUv"),
        lambda: montar(
            "ey", "JhbGciOiJIUzI1NiJ9", ".", "ey", "JzdWIiOiIxMjM0NTY3ODkw", ".", "abcDEF123_-xyz"
        ),
    ],
)
def test_procurar_segredos_acha_credenciais_de_nuvem_e_jwt(regras, linha):
    assert procurar_segredos([linha()], regras["segredos"])


def hook_sem_venv(tmp_path: Path, nome: str, *argumentos: str) -> subprocess.CompletedProcess:
    origem = (RAIZ / ".githooks" / nome).read_text(encoding="utf-8")
    destino = tmp_path / nome
    destino.write_text(origem, encoding="utf-8")
    destino.chmod(0o755)
    return subprocess.run(
        [str(destino), *argumentos],
        cwd=tmp_path,
        env=ambiente_sem_git(),
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("nome", ["pre-commit", "commit-msg"])
def test_hook_sem_venv_falha_com_mensagem_util(tmp_path, nome):
    resultado = hook_sem_venv(tmp_path, nome, str(tmp_path / "msg"))
    assert resultado.returncode != 0
    assert "falta .venv: rode make setup" in resultado.stderr


def test_expressoes_do_yaml_compilam(regras):
    assert compilar(regras["segredos"])
    assert compilar(regras["atribuicao"])


def test_pre_commit_roda_guarda_antes_dos_testes():
    hook = Path(".githooks/pre-commit")
    conteudo = hook.read_text(encoding="utf-8")
    assert os.access(hook, os.X_OK)
    assert conteudo.index("repositorio_guarda arquivos") < conteudo.index("repositorio_guarda diff")
    assert conteudo.index("repositorio_guarda diff") < conteudo.index("make testes")


def test_commit_msg_hook_chama_a_guarda():
    hook = Path(".githooks/commit-msg")
    conteudo = hook.read_text(encoding="utf-8")
    assert os.access(hook, os.X_OK)
    assert 'repositorio_guarda mensagem "$1"' in conteudo
