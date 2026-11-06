# Origem da skill legal-br

- Repositório: https://github.com/manfredjr/legal-br (pasta `legal-br-skill/legal-br`)
- Versão: 1.2.0 (`VERSION.txt`) · commit `583853a88abe562997b0047e318568e2c1b1e971` · acervo coletado em 21/08/2026 (`ULTIMA-ATUALIZACAO.txt`)
- Licença: MIT, Copyright (c) 2026 Manfred Tecnologia (`LICENSE`).
- Instalado em 26/10/2026, após leitura integral de SKILL.md, `references/` e `templates/` e varredura das fontes copiadas.
- Uso: SEGUNDA OPINIÃO, depois da `founder-juridico-br`. Gera `consulta-advogado` com perguntas fechadas.
- Copiado: só Markdown: SKILL.md, references, templates, FONTES-OFICIAIS.md e 9 arquivos de `fontes-md/` (CDC, LGPD, Decreto 7.962, Lei 14.063, guia de cookies ANPD, Res. ANPD 2/2022 e 15/2024).
- NÃO copiado: `.bat`, `.ps1`, `fontes/` (HTML/PDF originais), `CHECKSUMS`, `docs/`, `CLAUDE.md` do repositório de origem.
- O upstream manda rodar scripts `.bat` de verificação e cita um relatório de status das fontes; isso foi removido do SKILL.md (ver "Alterações" abaixo). Nada disso foi instalado.
- O SKILL.md cita `templates/consulta-advogado-externo.md`, que não existe no repositório de origem; use a estrutura descrita na seção "Escalonamento".
- Coleta de 21/08/2026: acervo não verificado contra a fonte oficial.

## Alterações em relação ao upstream (26/10/2026)
- `SKILL.md`: `description` e "regras" estreitadas para uso manual (só pedida pelo nome ou em revisão jurídica explícita).
- `SKILL.md`: removidas todas as instruções de executar `VERIFICAR-FONTES.bat`, `ATUALIZAR-FONTES.bat` e `VALIDAR-REVISAO.bat`, a tabela e as menções ao `STATUS-FONTES.md`. Troca: "não instalado neste projeto: trate o acervo local como não verificado e confirme a lei na fonte oficial (planalto.gov.br / gov.br/anpd) antes de citar".
- `SKILL.md`: a saída não é mais "sempre um `.md` ao lado do original"; só é gravada onde o usuário pedir (neste projeto, `docs/legal/`).
- `references/menores-imagem.md`: menção ao `STATUS-FONTES.md` trocada pela mesma regra.

## Cópia para o pleito (05/11/2026)
- Copiado sem alteração de texto do repositório CarroAberto, onde já estava revisado (ver acima).
- No pleito o uso continua manual. O caso real é `docs/privacidade.md`, a política pública exigida pelo Google para o OAuth do Gmail (F1.1). Relatório, quando pedido, vai para `docs/legal/`.
- Nada de dado pessoal do currículo, email ou telefone entra no relatório.
