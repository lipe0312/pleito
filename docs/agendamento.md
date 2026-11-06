# Agendamento por launchd

Fonte única: o bloco `agendamento` e `horarios` de `config/limites.yaml`. O plist não é
versionado e nunca é instalado pelo agente.

## Como funciona

- `make agendamento-plist` gera `dados/agendamento/br.pleito.rotinas.plist` com uma janela
  `StartCalendarInterval` por rotina de horário fixo e um `StartInterval` pelo menor intervalo
  de rotina periódica; `RunAtLoad` fica ligado.
- Cada disparo roda `python -m src.agendamento.executor`, que decide por rotina:
  - horário fixo: roda a janela mais recente ainda não registrada; se o atraso passar de
    `tolerancia_min` (Mac dormindo) e `retry_ao_acordar` for verdadeiro, roda uma vez e marca
    `recuperada`; se for falso, registra `perdida` e não roda;
  - intervalo: roda quando o intervalo menos a tolerância passou desde a última execução.
- O registro fica em `dados/agendamento/execucoes.json` (fora do git).

## Instalação manual (item M3)

1. `make agendamento-plist`
2. `cp dados/agendamento/br.pleito.rotinas.plist ~/Library/LaunchAgents/`
3. `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/br.pleito.rotinas.plist`
4. Conferir: `launchctl print gui/$(id -u)/br.pleito.rotinas`

O rótulo vem de `agendamento.rotulo`. Para remover: `launchctl bootout gui/$(id -u)/<rótulo>`.

## Despertar do Mac (pmset)

Comando manual, com o horário de `horarios.descoberta` menos alguns minutos de folga (ADR 0014):

    sudo pmset repeat wakeorpoweron MTWRFSU 06:25:00

Conferir com `pmset -g sched`; cancelar com `sudo pmset repeat cancel`. O agente nunca roda
`sudo` nem `pmset`.
