BEGIN;

SET search_path TO pleito, public;

ALTER TABLE uso_llm
    ADD COLUMN prompt_versao text NOT NULL DEFAULT 'indefinida',
    ADD COLUMN custo_reservado_usd numeric(12,9) NOT NULL DEFAULT 0,
    ADD COLUMN resultado_validacao text NOT NULL DEFAULT 'pendente',
    ADD COLUMN estado text NOT NULL DEFAULT 'reservado',
    ADD COLUMN erro_tipo text,
    ADD COLUMN concluido_em timestamptz;

UPDATE uso_llm SET custo_usd = 0 WHERE custo_usd IS NULL;

ALTER TABLE uso_llm
    ALTER COLUMN custo_usd SET DEFAULT 0,
    ALTER COLUMN custo_usd SET NOT NULL,
    ALTER COLUMN custo_usd TYPE numeric(12,9);

ALTER TABLE uso_llm
    ADD CONSTRAINT uso_llm_tokens_nao_negativos
        CHECK (tokens_entrada >= 0 AND tokens_saida >= 0),
    ADD CONSTRAINT uso_llm_custos_nao_negativos
        CHECK (custo_usd >= 0 AND custo_reservado_usd >= 0),
    ADD CONSTRAINT uso_llm_estado_valido
        CHECK (estado IN ('reservado', 'concluido', 'falhou'));

CREATE INDEX uso_llm_ocorrido_em_idx ON uso_llm (ocorrido_em);

CREATE FUNCTION atualizar_flag_alterada_em() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO pleito, pg_temp
AS $$
BEGIN
    NEW.alterada_em = now();
    RETURN NEW;
END
$$;

CREATE TRIGGER flag_sistema_alterada_em
    BEFORE UPDATE ON flag_sistema
    FOR EACH ROW EXECUTE FUNCTION atualizar_flag_alterada_em();

COMMIT;
