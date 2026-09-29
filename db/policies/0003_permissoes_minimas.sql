BEGIN;

SET search_path TO pleito, public;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pleito_painel_login') THEN
        CREATE ROLE pleito_painel_login NOLOGIN IN ROLE pleito_painel;
    END IF;
END
$$;

REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA pleito
    FROM pleito_app, pleito_painel, pleito_leitura;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA pleito
    FROM pleito_app, pleito_painel, pleito_leitura;

GRANT USAGE ON SCHEMA pleito TO pleito_app, pleito_painel, pleito_leitura;
GRANT SELECT ON ALL TABLES IN SCHEMA pleito
    TO pleito_app, pleito_painel, pleito_leitura;
GRANT USAGE, SELECT ON SEQUENCE
    vaga_id_seq,
    versao_curriculo_id_seq,
    candidatura_id_seq,
    pendencia_id_seq,
    evento_email_id_seq,
    uso_llm_id_seq,
    auditoria_id_seq,
    execucao_viabilidade_id_seq
    TO pleito_app;
GRANT USAGE, SELECT ON SEQUENCE
    aprovacao_id_seq,
    pendencia_id_seq,
    resposta_banco_id_seq,
    auditoria_id_seq
    TO pleito_painel;

GRANT INSERT (
    fonte_id,
    empresa_id,
    id_externo,
    url,
    titulo,
    descricao,
    local,
    pais,
    senioridade,
    modelo,
    idioma_anuncio,
    publicada_em,
    hash_conteudo
) ON vaga TO pleito_app;
GRANT UPDATE (
    empresa_id,
    titulo,
    descricao,
    local,
    pais,
    senioridade,
    modelo,
    idioma_anuncio,
    publicada_em,
    coletada_em,
    hash_conteudo,
    estado,
    nota,
    motivo_descarte
) ON vaga TO pleito_app;
GRANT UPDATE (alvo) ON empresa TO pleito_painel;
GRANT UPDATE (ativa) ON fonte TO pleito_painel;

GRANT INSERT (
    vaga_id,
    familia,
    idioma,
    numero,
    caminho_tex,
    caminho_pdf,
    hash_pdf,
    paginas,
    linhas_livres,
    validacao
) ON versao_curriculo TO pleito_app;
GRANT INSERT (vaga_id, versao_id, hash_aprovado, expira_em) ON aprovacao TO pleito_painel;
GRANT UPDATE (consumida_em) ON aprovacao TO pleito_app;

GRANT INSERT (vaga_id, versao_id, aprovacao_id, plataforma, manual) ON candidatura TO pleito_app;
GRANT UPDATE (prova, prova_em, captura_tela) ON candidatura TO pleito_app;

GRANT INSERT (vaga_id, categoria, detalhe, link) ON pendencia TO pleito_app;
GRANT UPDATE (resolvida_em) ON pendencia TO pleito_app, pleito_painel;

GRANT INSERT (pergunta, resposta, idioma, familia) ON resposta_banco TO pleito_painel;
GRANT UPDATE (resposta, aprovada_em) ON resposta_banco TO pleito_painel;

GRANT INSERT (
    vaga_id,
    id_mensagem,
    remetente,
    dominio,
    autenticado,
    tipo,
    confianca,
    payload,
    recebido_em
) ON evento_email TO pleito_app;
GRANT UPDATE (aplicado) ON evento_email TO pleito_app;

GRANT INSERT (
    etapa,
    provedor,
    modelo,
    tier,
    prompt_versao,
    custo_reservado_usd
) ON uso_llm TO pleito_app;
GRANT UPDATE (
    tokens_entrada,
    tokens_saida,
    custo_usd,
    custo_reservado_usd,
    resultado_validacao,
    estado,
    erro_tipo,
    concluido_em
) ON uso_llm TO pleito_app;
GRANT INSERT (ator, acao, entidade, entidade_id, antes, depois)
    ON auditoria TO pleito_app, pleito_painel;
GRANT UPDATE (ligada, motivo) ON flag_sistema TO pleito_painel;
GRANT INSERT (
    fonte_id,
    etapa,
    veredito,
    vagas_obtidas,
    completude,
    http_status,
    robots_permite,
    erro,
    evidencia
) ON execucao_viabilidade TO pleito_app;

ALTER TABLE uso_llm ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS uso_llm_leitura ON uso_llm;
DROP POLICY IF EXISTS uso_llm_escrita ON uso_llm;

CREATE POLICY uso_llm_leitura ON uso_llm
    FOR SELECT TO pleito_leitura, pleito_app, pleito_painel USING (true);
CREATE POLICY uso_llm_escrita ON uso_llm
    FOR INSERT TO pleito_app WITH CHECK (
        custo_usd >= 0
        AND custo_reservado_usd >= 0
        AND estado IN ('reservado', 'concluido', 'falhou')
    );
CREATE POLICY uso_llm_atualiza ON uso_llm
    FOR UPDATE TO pleito_app
    USING (estado = 'reservado')
    WITH CHECK (estado IN ('concluido', 'falhou'));

DROP POLICY IF EXISTS candidatura_cria ON candidatura;
CREATE POLICY candidatura_cria ON candidatura FOR INSERT TO pleito_app WITH CHECK (
    EXISTS (
        SELECT 1
        FROM aprovacao a
        JOIN versao_curriculo vc ON vc.id = a.versao_id
        WHERE a.id = candidatura.aprovacao_id
          AND a.vaga_id = candidatura.vaga_id
          AND a.versao_id = candidatura.versao_id
          AND a.consumida_em IS NOT NULL
          AND a.hash_aprovado = vc.hash_pdf
    )
);

COMMIT;
