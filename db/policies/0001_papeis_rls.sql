BEGIN;

SET search_path TO pleito, public;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pleito_app') THEN
        CREATE ROLE pleito_app NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pleito_leitura') THEN
        CREATE ROLE pleito_leitura NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pleito_painel') THEN
        CREATE ROLE pleito_painel NOLOGIN;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA pleito TO pleito_app, pleito_leitura, pleito_painel;

GRANT SELECT ON ALL TABLES IN SCHEMA pleito TO pleito_leitura;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA pleito TO pleito_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA pleito TO pleito_painel;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA pleito TO pleito_app, pleito_painel;

REVOKE INSERT, UPDATE, DELETE ON auditoria FROM pleito_app, pleito_painel;
GRANT INSERT ON auditoria TO pleito_app, pleito_painel;
GRANT USAGE ON SEQUENCE auditoria_id_seq TO pleito_app, pleito_painel;

REVOKE UPDATE, DELETE ON candidatura FROM pleito_app;
GRANT INSERT, SELECT, UPDATE ON candidatura TO pleito_app;

ALTER TABLE vaga ENABLE ROW LEVEL SECURITY;
ALTER TABLE versao_curriculo ENABLE ROW LEVEL SECURITY;
ALTER TABLE aprovacao ENABLE ROW LEVEL SECURITY;
ALTER TABLE candidatura ENABLE ROW LEVEL SECURITY;
ALTER TABLE evento_email ENABLE ROW LEVEL SECURITY;
ALTER TABLE flag_sistema ENABLE ROW LEVEL SECURITY;
ALTER TABLE resposta_banco ENABLE ROW LEVEL SECURITY;

CREATE POLICY vaga_leitura ON vaga FOR SELECT TO pleito_leitura, pleito_app, pleito_painel USING (true);
CREATE POLICY vaga_escrita ON vaga FOR INSERT TO pleito_app WITH CHECK (true);
CREATE POLICY vaga_atualiza ON vaga FOR UPDATE TO pleito_app, pleito_painel USING (true) WITH CHECK (true);

CREATE POLICY versao_leitura ON versao_curriculo FOR SELECT TO pleito_leitura, pleito_app, pleito_painel USING (true);
CREATE POLICY versao_escrita ON versao_curriculo FOR INSERT TO pleito_app WITH CHECK (paginas = 1);
CREATE POLICY versao_atualiza ON versao_curriculo FOR UPDATE TO pleito_painel USING (true) WITH CHECK (paginas = 1);

CREATE POLICY aprovacao_leitura ON aprovacao FOR SELECT TO pleito_app, pleito_painel USING (true);
CREATE POLICY aprovacao_cria ON aprovacao FOR INSERT TO pleito_painel WITH CHECK (expira_em > now());
CREATE POLICY aprovacao_consome ON aprovacao FOR UPDATE TO pleito_app
    USING (consumida_em IS NULL AND expira_em > now())
    WITH CHECK (consumida_em IS NOT NULL);

CREATE POLICY candidatura_leitura ON candidatura FOR SELECT TO pleito_leitura, pleito_app, pleito_painel USING (true);
CREATE POLICY candidatura_cria ON candidatura FOR INSERT TO pleito_app WITH CHECK (true);
CREATE POLICY candidatura_prova ON candidatura FOR UPDATE TO pleito_app, pleito_painel USING (true) WITH CHECK (true);

CREATE POLICY evento_leitura ON evento_email FOR SELECT TO pleito_leitura, pleito_app, pleito_painel USING (true);
CREATE POLICY evento_cria ON evento_email FOR INSERT TO pleito_app WITH CHECK (autenticado OR confianca < 1.0);
CREATE POLICY evento_aplica ON evento_email FOR UPDATE TO pleito_app, pleito_painel USING (true) WITH CHECK (true);

CREATE POLICY flag_leitura ON flag_sistema FOR SELECT TO pleito_leitura, pleito_app, pleito_painel USING (true);
CREATE POLICY flag_altera ON flag_sistema FOR UPDATE TO pleito_painel USING (true) WITH CHECK (true);

CREATE POLICY resposta_leitura ON resposta_banco FOR SELECT TO pleito_leitura, pleito_app, pleito_painel USING (aprovada_em IS NOT NULL);
CREATE POLICY resposta_cria ON resposta_banco FOR INSERT TO pleito_painel WITH CHECK (true);
CREATE POLICY resposta_aprova ON resposta_banco FOR UPDATE TO pleito_painel USING (true) WITH CHECK (true);

COMMIT;
