BEGIN;

SET search_path TO pleito, public;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pleito_chat') THEN
        CREATE ROLE pleito_chat NOLOGIN;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA pleito TO pleito_chat;

GRANT SELECT ON transicao_estado_vaga, historico_versao_curriculo
    TO pleito_app, pleito_painel, pleito_leitura;
GRANT SELECT ON versao_curriculo, vaga TO pleito_chat;

GRANT INSERT (prompt_versao, modelo, origem) ON versao_curriculo TO pleito_app;
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
    validacao,
    prompt_versao,
    modelo,
    origem
) ON versao_curriculo TO pleito_chat;
GRANT USAGE, SELECT ON SEQUENCE versao_curriculo_id_seq TO pleito_chat;

DROP POLICY IF EXISTS versao_escrita ON versao_curriculo;
CREATE POLICY versao_escrita ON versao_curriculo FOR INSERT TO pleito_app
    WITH CHECK (paginas = 1 AND origem IN ('gerada', 'refeita'));

CREATE POLICY versao_escrita_chat ON versao_curriculo FOR INSERT TO pleito_chat
    WITH CHECK (
        paginas = 1
        AND origem = 'chat'
        AND EXISTS (
            SELECT 1
            FROM vaga v
            WHERE v.id = versao_curriculo.vaga_id
              AND v.estado IN ('aguardando_aprovacao', 'aprovada')
        )
    );

CREATE POLICY versao_leitura_chat ON versao_curriculo FOR SELECT TO pleito_chat USING (true);
CREATE POLICY vaga_leitura_chat ON vaga FOR SELECT TO pleito_chat USING (true);

DROP POLICY IF EXISTS versao_atualiza ON versao_curriculo;

DROP POLICY IF EXISTS aprovacao_cria ON aprovacao;
CREATE POLICY aprovacao_cria ON aprovacao FOR INSERT TO pleito_painel WITH CHECK (
    expira_em > now()
    AND invalidada_em IS NULL
    AND consumida_em IS NULL
    AND EXISTS (
        SELECT 1
        FROM versao_curriculo vc
        WHERE vc.id = aprovacao.versao_id
          AND vc.vaga_id = aprovacao.vaga_id
          AND vc.hash_pdf = aprovacao.hash_aprovado
          AND vc.numero = (
              SELECT MAX(ultima.numero) FROM versao_curriculo ultima WHERE ultima.vaga_id = vc.vaga_id
          )
    )
);

DROP POLICY IF EXISTS aprovacao_consome ON aprovacao;
CREATE POLICY aprovacao_consome ON aprovacao FOR UPDATE TO pleito_app
    USING (
        consumida_em IS NULL
        AND invalidada_em IS NULL
        AND expira_em > now()
        AND EXISTS (
            SELECT 1
            FROM versao_curriculo vc
            WHERE vc.id = aprovacao.versao_id
              AND vc.numero = (
                  SELECT MAX(ultima.numero) FROM versao_curriculo ultima
                  WHERE ultima.vaga_id = vc.vaga_id
              )
        )
    )
    WITH CHECK (consumida_em IS NOT NULL);

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
          AND a.invalidada_em IS NULL
          AND a.hash_aprovado = vc.hash_pdf
          AND vc.numero = (
              SELECT MAX(ultima.numero) FROM versao_curriculo ultima WHERE ultima.vaga_id = vc.vaga_id
          )
    )
);

COMMIT;
