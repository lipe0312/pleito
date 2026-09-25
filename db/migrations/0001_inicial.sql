BEGIN;

CREATE SCHEMA IF NOT EXISTS pleito;
SET search_path TO pleito, public;

CREATE TYPE senioridade AS ENUM ('estagio', 'junior', 'pleno', 'senior', 'indefinida');
CREATE TYPE modelo_trabalho AS ENUM ('remoto', 'hibrido', 'presencial', 'indefinido');
CREATE TYPE idioma AS ENUM ('pt', 'en');
CREATE TYPE familia AS ENUM ('backend', 'dados', 'fullstack', 'ia');

CREATE TYPE estado_vaga AS ENUM (
    'descoberta',
    'triada',
    'pontuada',
    'variante_gerada',
    'aguardando_aprovacao',
    'aprovada',
    'aplicada_aguardando_confirmacao',
    'aplicada_confirmada',
    'aplicada_nao_confirmada',
    'pendente',
    'entrevista',
    'teste',
    'rejeitada_pelo_filipe',
    'rejeitada_pela_empresa',
    'encerrada'
);

CREATE TYPE veredito_viabilidade AS ENUM ('go', 'go_com_ressalva', 'no_go', 'nao_testado');
CREATE TYPE nivel_prova AS ENUM ('pagina_confirmacao', 'email_plataforma', 'confirmacao_manual');
CREATE TYPE nivel_curriculo AS ENUM ('base', 'forte', 'campeao');

CREATE TABLE fonte (
    id              smallserial PRIMARY KEY,
    slug            text NOT NULL UNIQUE,
    nome            text NOT NULL,
    tipo            text NOT NULL,
    dominio         text,
    veredito        veredito_viabilidade NOT NULL DEFAULT 'nao_testado',
    robots_permite  boolean,
    tos_revisado_em date,
    ativa           boolean NOT NULL DEFAULT false,
    observacao      text,
    criada_em       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE empresa (
    id          bigserial PRIMARY KEY,
    nome        text NOT NULL,
    nome_norm   text GENERATED ALWAYS AS (lower(btrim(nome))) STORED,
    dominio     text,
    alvo        boolean NOT NULL DEFAULT false,
    porte       text,
    setor       text,
    pais        text,
    criada_em   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT empresa_nome_unica UNIQUE (nome_norm)
);

CREATE TABLE vaga (
    id                bigserial PRIMARY KEY,
    fonte_id          smallint NOT NULL REFERENCES fonte(id),
    empresa_id        bigint REFERENCES empresa(id),
    id_externo        text NOT NULL,
    url               text NOT NULL,
    titulo            text NOT NULL,
    descricao         text NOT NULL DEFAULT '',
    local             text,
    pais              text,
    senioridade       senioridade NOT NULL DEFAULT 'indefinida',
    modelo            modelo_trabalho NOT NULL DEFAULT 'indefinido',
    idioma_anuncio    idioma,
    publicada_em      date,
    coletada_em       timestamptz NOT NULL DEFAULT now(),
    hash_conteudo     bytea NOT NULL,
    estado            estado_vaga NOT NULL DEFAULT 'descoberta',
    nota              numeric(4,1),
    motivo_descarte   text,
    CONSTRAINT vaga_unica_por_fonte UNIQUE (fonte_id, id_externo),
    CONSTRAINT vaga_nota_faixa CHECK (nota IS NULL OR (nota >= 0 AND nota <= 100))
);

CREATE INDEX vaga_estado_idx ON vaga (estado);
CREATE INDEX vaga_coletada_idx ON vaga (coletada_em DESC);
CREATE INDEX vaga_hash_idx ON vaga (hash_conteudo);

CREATE TABLE versao_curriculo (
    id            bigserial PRIMARY KEY,
    vaga_id       bigint REFERENCES vaga(id) ON DELETE CASCADE,
    familia       familia NOT NULL,
    idioma        idioma NOT NULL,
    numero        integer NOT NULL DEFAULT 1,
    nivel         nivel_curriculo NOT NULL DEFAULT 'base',
    caminho_tex   text NOT NULL,
    caminho_pdf   text NOT NULL,
    hash_pdf      bytea NOT NULL,
    paginas       smallint NOT NULL,
    linhas_livres numeric(4,2),
    validacao     jsonb NOT NULL DEFAULT '{}'::jsonb,
    protegida     boolean NOT NULL DEFAULT false,
    criada_em     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT versao_uma_pagina CHECK (paginas = 1),
    CONSTRAINT versao_unica UNIQUE (vaga_id, familia, idioma, numero)
);

CREATE TABLE aprovacao (
    id             bigserial PRIMARY KEY,
    vaga_id        bigint NOT NULL REFERENCES vaga(id) ON DELETE CASCADE,
    versao_id      bigint NOT NULL REFERENCES versao_curriculo(id) ON DELETE CASCADE,
    token          uuid NOT NULL DEFAULT gen_random_uuid(),
    hash_aprovado  bytea NOT NULL,
    consumida_em   timestamptz,
    expira_em      timestamptz NOT NULL,
    criada_em      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT aprovacao_token_unico UNIQUE (token)
);

CREATE TABLE candidatura (
    id              bigserial PRIMARY KEY,
    vaga_id         bigint NOT NULL REFERENCES vaga(id) ON DELETE CASCADE,
    versao_id       bigint NOT NULL REFERENCES versao_curriculo(id),
    aprovacao_id    bigint NOT NULL REFERENCES aprovacao(id),
    plataforma      text NOT NULL,
    enviada_em      timestamptz NOT NULL DEFAULT now(),
    prova           nivel_prova,
    prova_em        timestamptz,
    captura_tela    text,
    manual          boolean NOT NULL DEFAULT false,
    CONSTRAINT candidatura_unica UNIQUE (vaga_id)
);

CREATE TABLE pendencia (
    id          bigserial PRIMARY KEY,
    vaga_id     bigint NOT NULL REFERENCES vaga(id) ON DELETE CASCADE,
    categoria   text NOT NULL,
    detalhe     text NOT NULL,
    link        text,
    resolvida_em timestamptz,
    criada_em   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE resposta_banco (
    id            bigserial PRIMARY KEY,
    pergunta      text NOT NULL,
    pergunta_norm text GENERATED ALWAYS AS (lower(btrim(pergunta))) STORED,
    resposta      text NOT NULL,
    idioma        idioma NOT NULL,
    familia       familia,
    aprovada_em   timestamptz,
    CONSTRAINT resposta_unica UNIQUE (pergunta_norm, idioma, familia)
);

CREATE TABLE evento_email (
    id              bigserial PRIMARY KEY,
    vaga_id         bigint REFERENCES vaga(id) ON DELETE SET NULL,
    id_mensagem     text NOT NULL UNIQUE,
    remetente       text NOT NULL,
    dominio         text,
    autenticado     boolean NOT NULL DEFAULT false,
    tipo            text NOT NULL,
    confianca       numeric(3,2) NOT NULL,
    payload         jsonb NOT NULL DEFAULT '{}'::jsonb,
    aplicado        boolean NOT NULL DEFAULT false,
    recebido_em     timestamptz NOT NULL,
    CONSTRAINT evento_confianca_faixa CHECK (confianca >= 0 AND confianca <= 1)
);

CREATE TABLE uso_llm (
    id              bigserial PRIMARY KEY,
    vaga_id         bigint REFERENCES vaga(id) ON DELETE SET NULL,
    etapa           text NOT NULL,
    provedor        text NOT NULL,
    modelo          text NOT NULL,
    tier            text NOT NULL,
    tokens_entrada  integer NOT NULL DEFAULT 0,
    tokens_saida    integer NOT NULL DEFAULT 0,
    custo_usd       numeric(10,6),
    ocorrido_em     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE auditoria (
    id          bigserial PRIMARY KEY,
    ator        text NOT NULL,
    acao        text NOT NULL,
    entidade    text NOT NULL,
    entidade_id text,
    antes       jsonb,
    depois      jsonb,
    ocorrido_em timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX auditoria_entidade_idx ON auditoria (entidade, entidade_id);

CREATE TABLE flag_sistema (
    chave       text PRIMARY KEY,
    ligada      boolean NOT NULL,
    motivo      text,
    alterada_em timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE execucao_viabilidade (
    id             bigserial PRIMARY KEY,
    fonte_id       smallint REFERENCES fonte(id),
    etapa          text NOT NULL,
    veredito       veredito_viabilidade NOT NULL,
    vagas_obtidas  integer NOT NULL DEFAULT 0,
    completude     numeric(4,3),
    http_status    integer,
    robots_permite boolean,
    erro           text,
    evidencia      jsonb NOT NULL DEFAULT '{}'::jsonb,
    ocorrido_em    timestamptz NOT NULL DEFAULT now()
);

INSERT INTO flag_sistema (chave, ligada, motivo) VALUES
    ('sistema_ativo', false, 'desligado ate o spike de viabilidade fechar GO'),
    ('egress_submit_real', false, 'submit real exige autorizacao explicita por execucao');

INSERT INTO fonte (slug, nome, tipo, dominio, veredito) VALUES
    ('greenhouse', 'Greenhouse', 'api_publica', 'boards-api.greenhouse.io', 'nao_testado'),
    ('lever', 'Lever', 'api_publica', 'api.lever.co', 'nao_testado'),
    ('ashby', 'Ashby', 'api_publica', 'api.ashbyhq.com', 'nao_testado'),
    ('gupy', 'Gupy', 'portal_investigacao', 'portal.api.gupy.io', 'nao_testado'),
    ('solides', 'Solides', 'portal_investigacao', 'vagas.solides.com.br', 'nao_testado'),
    ('linkedin_alertas', 'LinkedIn (alertas por email)', 'email_alerta', NULL, 'nao_testado');

COMMIT;
