BEGIN;

SET search_path TO pleito, public;

CREATE TYPE origem_versao AS ENUM ('gerada', 'refeita', 'chat');

ALTER TABLE versao_curriculo
    ADD COLUMN prompt_versao text NOT NULL DEFAULT 'indefinida',
    ADD COLUMN modelo text NOT NULL DEFAULT 'indefinido',
    ADD COLUMN origem origem_versao NOT NULL DEFAULT 'gerada';

CREATE UNIQUE INDEX versao_numero_por_vaga
    ON versao_curriculo (vaga_id, numero)
    WHERE vaga_id IS NOT NULL;

ALTER TABLE aprovacao
    ADD COLUMN invalidada_em timestamptz,
    ADD COLUMN invalidada_por_versao_id bigint REFERENCES versao_curriculo(id) ON DELETE SET NULL;

CREATE INDEX aprovacao_vaga_valida_idx
    ON aprovacao (vaga_id)
    WHERE invalidada_em IS NULL AND consumida_em IS NULL;

CREATE FUNCTION impedir_alteracao_de_versao() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO pleito, pg_temp
AS $$
BEGIN
    IF (to_jsonb(NEW) - 'nivel' - 'protegida') IS DISTINCT FROM (to_jsonb(OLD) - 'nivel' - 'protegida') THEN
        RAISE EXCEPTION 'versao de curriculo e imutavel: so nivel e protegida mudam'
            USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END
$$;

CREATE TRIGGER versao_curriculo_imutavel
    BEFORE UPDATE ON versao_curriculo
    FOR EACH ROW EXECUTE FUNCTION impedir_alteracao_de_versao();

CREATE FUNCTION exigir_numero_sequencial_de_versao() RETURNS trigger
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path TO pleito, pg_temp
AS $$
BEGIN
    IF NEW.vaga_id IS NOT NULL THEN
        PERFORM 1 FROM vaga WHERE id = NEW.vaga_id FOR NO KEY UPDATE;
    END IF;
    IF NEW.vaga_id IS NOT NULL
        AND NEW.numero IS DISTINCT FROM (
            SELECT COALESCE(MAX(numero), 0) + 1 FROM versao_curriculo WHERE vaga_id = NEW.vaga_id
        )
    THEN
        RAISE EXCEPTION 'numero de versao fora de sequencia na vaga %', NEW.vaga_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$;

CREATE TRIGGER versao_curriculo_numero
    BEFORE INSERT ON versao_curriculo
    FOR EACH ROW EXECUTE FUNCTION exigir_numero_sequencial_de_versao();

CREATE FUNCTION invalidar_aprovacao_por_nova_versao() RETURNS trigger
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path TO pleito, pg_temp
AS $$
BEGIN
    IF NEW.vaga_id IS NULL THEN
        RETURN NEW;
    END IF;
    WITH alvo AS (
        SELECT id
        FROM aprovacao
        WHERE vaga_id = NEW.vaga_id
          AND versao_id <> NEW.id
          AND invalidada_em IS NULL
          AND consumida_em IS NULL
        FOR UPDATE SKIP LOCKED
    ),
    invalidadas AS (
        UPDATE aprovacao a
        SET invalidada_em = now(), invalidada_por_versao_id = NEW.id
        FROM alvo
        WHERE a.id = alvo.id
        RETURNING a.id, a.versao_id
    )
    INSERT INTO auditoria (ator, acao, entidade, entidade_id, antes, depois)
    SELECT 'banco', 'invalidar_aprovacao', 'aprovacao', id::text,
           jsonb_build_object('versao_id', versao_id),
           jsonb_build_object('invalidada_por_versao_id', NEW.id)
    FROM invalidadas;
    UPDATE vaga SET estado = 'aguardando_aprovacao'
    WHERE id = NEW.vaga_id AND estado = 'aprovada';
    RETURN NEW;
END
$$;

CREATE TRIGGER versao_curriculo_invalida_aprovacao
    AFTER INSERT ON versao_curriculo
    FOR EACH ROW EXECUTE FUNCTION invalidar_aprovacao_por_nova_versao();

CREATE FUNCTION auditar_versao_do_chat() RETURNS trigger
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path TO pleito, pg_temp
AS $$
BEGIN
    INSERT INTO auditoria (ator, acao, entidade, entidade_id, depois)
    VALUES (
        'chat', 'criar_versao', 'versao_curriculo', NEW.id::text,
        jsonb_build_object('vaga_id', NEW.vaga_id, 'numero', NEW.numero, 'hash_pdf', encode(NEW.hash_pdf, 'hex'))
    );
    RETURN NEW;
END
$$;

CREATE TRIGGER versao_curriculo_auditoria_do_chat
    AFTER INSERT ON versao_curriculo
    FOR EACH ROW
    WHEN (NEW.origem = 'chat')
    EXECUTE FUNCTION auditar_versao_do_chat();

CREATE FUNCTION exigir_ultima_versao_na_candidatura() RETURNS trigger
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path TO pleito, pg_temp
AS $$
BEGIN
    PERFORM 1 FROM vaga WHERE id = NEW.vaga_id FOR NO KEY UPDATE;
    IF NOT EXISTS (
        SELECT 1
        FROM versao_curriculo vc
        WHERE vc.id = NEW.versao_id
          AND vc.vaga_id = NEW.vaga_id
          AND vc.numero = (SELECT MAX(numero) FROM versao_curriculo WHERE vaga_id = NEW.vaga_id)
    ) THEN
        RAISE EXCEPTION 'candidatura recusada: a versao nao e a ultima da vaga %', NEW.vaga_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$;

CREATE TRIGGER candidatura_ultima_versao
    BEFORE INSERT ON candidatura
    FOR EACH ROW EXECUTE FUNCTION exigir_ultima_versao_na_candidatura();

CREATE FUNCTION exigir_ultima_versao_na_aprovacao() RETURNS trigger
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path TO pleito, pg_temp
AS $$
BEGIN
    PERFORM 1 FROM vaga WHERE id = NEW.vaga_id FOR NO KEY UPDATE;
    IF NOT EXISTS (
        SELECT 1
        FROM versao_curriculo vc
        WHERE vc.id = NEW.versao_id
          AND vc.vaga_id = NEW.vaga_id
          AND vc.hash_pdf = NEW.hash_aprovado
          AND vc.numero = (SELECT MAX(numero) FROM versao_curriculo WHERE vaga_id = NEW.vaga_id)
    ) THEN
        RAISE EXCEPTION 'aprovacao recusada: so vale para a ultima versao da vaga %, com o hash dela', NEW.vaga_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$;

CREATE TRIGGER aprovacao_ultima_versao
    BEFORE INSERT ON aprovacao
    FOR EACH ROW EXECUTE FUNCTION exigir_ultima_versao_na_aprovacao();

CREATE TABLE transicao_estado_vaga (
    origem  estado_vaga NOT NULL,
    destino estado_vaga NOT NULL,
    PRIMARY KEY (origem, destino),
    CONSTRAINT transicao_muda_de_estado CHECK (origem <> destino)
);

INSERT INTO transicao_estado_vaga (origem, destino) VALUES
    ('descoberta', 'triada'),
    ('triada', 'pontuada'),
    ('pontuada', 'variante_gerada'),
    ('variante_gerada', 'aguardando_aprovacao'),
    ('aguardando_aprovacao', 'aprovada'),
    ('aguardando_aprovacao', 'rejeitada_pelo_filipe'),
    ('aprovada', 'aguardando_aprovacao'),
    ('aprovada', 'aplicada_aguardando_confirmacao'),
    ('aprovada', 'pendente'),
    ('pendente', 'aplicada_aguardando_confirmacao'),
    ('pendente', 'aplicada_confirmada'),
    ('aplicada_aguardando_confirmacao', 'aplicada_confirmada'),
    ('aplicada_aguardando_confirmacao', 'aplicada_nao_confirmada'),
    ('aplicada_nao_confirmada', 'aplicada_confirmada'),
    ('aplicada_aguardando_confirmacao', 'teste'),
    ('aplicada_confirmada', 'teste'),
    ('aplicada_nao_confirmada', 'teste'),
    ('pendente', 'teste'),
    ('aplicada_aguardando_confirmacao', 'entrevista'),
    ('aplicada_confirmada', 'entrevista'),
    ('aplicada_nao_confirmada', 'entrevista'),
    ('pendente', 'entrevista'),
    ('teste', 'entrevista'),
    ('aplicada_aguardando_confirmacao', 'oferta'),
    ('aplicada_confirmada', 'oferta'),
    ('aplicada_nao_confirmada', 'oferta'),
    ('pendente', 'oferta'),
    ('teste', 'oferta'),
    ('entrevista', 'oferta'),
    ('aplicada_aguardando_confirmacao', 'rejeitada_pela_empresa'),
    ('aplicada_confirmada', 'rejeitada_pela_empresa'),
    ('aplicada_nao_confirmada', 'rejeitada_pela_empresa'),
    ('pendente', 'rejeitada_pela_empresa'),
    ('teste', 'rejeitada_pela_empresa'),
    ('entrevista', 'rejeitada_pela_empresa'),
    ('oferta', 'rejeitada_pela_empresa'),
    ('aplicada_aguardando_confirmacao', 'encerrada'),
    ('aplicada_confirmada', 'encerrada'),
    ('aplicada_nao_confirmada', 'encerrada'),
    ('pendente', 'encerrada'),
    ('teste', 'encerrada'),
    ('entrevista', 'encerrada'),
    ('oferta', 'encerrada');

CREATE FUNCTION validar_transicao_de_estado_da_vaga() RETURNS trigger
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path TO pleito, pg_temp
AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM transicao_estado_vaga WHERE origem = OLD.estado AND destino = NEW.estado
    ) THEN
        RAISE EXCEPTION 'transicao de estado recusada: % para %', OLD.estado, NEW.estado
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.estado = 'aprovada' AND NOT EXISTS (
        SELECT 1
        FROM aprovacao a
        JOIN versao_curriculo vc ON vc.id = a.versao_id
        WHERE a.vaga_id = NEW.id
          AND a.consumida_em IS NULL
          AND a.invalidada_em IS NULL
          AND a.expira_em > now()
          AND a.hash_aprovado = vc.hash_pdf
          AND vc.numero = (SELECT MAX(numero) FROM versao_curriculo WHERE vaga_id = NEW.id)
    ) THEN
        RAISE EXCEPTION 'transicao de estado recusada: aprovada exige aprovacao valida e nao consumida da ultima versao'
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.estado IN ('aplicada_aguardando_confirmacao', 'aplicada_confirmada', 'aplicada_nao_confirmada')
        AND NOT EXISTS (SELECT 1 FROM candidatura WHERE vaga_id = NEW.id)
    THEN
        RAISE EXCEPTION 'transicao de estado recusada: aplicada exige candidatura da vaga'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$;

CREATE TRIGGER vaga_transicao_de_estado
    BEFORE UPDATE OF estado ON vaga
    FOR EACH ROW
    WHEN (OLD.estado IS DISTINCT FROM NEW.estado)
    EXECUTE FUNCTION validar_transicao_de_estado_da_vaga();

REVOKE EXECUTE ON FUNCTION
    impedir_alteracao_de_versao(),
    exigir_numero_sequencial_de_versao(),
    invalidar_aprovacao_por_nova_versao(),
    auditar_versao_do_chat(),
    exigir_ultima_versao_na_candidatura(),
    exigir_ultima_versao_na_aprovacao(),
    validar_transicao_de_estado_da_vaga()
    FROM PUBLIC;

CREATE VIEW historico_versao_curriculo WITH (security_invoker = true) AS
SELECT
    vc.id,
    vc.vaga_id,
    vc.numero,
    vc.familia,
    vc.idioma,
    vc.nivel,
    vc.origem,
    vc.hash_pdf,
    vc.prompt_versao,
    vc.modelo,
    vc.caminho_tex,
    vc.caminho_pdf,
    vc.validacao,
    vc.paginas,
    vc.linhas_livres,
    vc.protegida,
    vc.criada_em,
    EXISTS (
        SELECT 1 FROM aprovacao a
        WHERE a.versao_id = vc.id
          AND a.invalidada_em IS NULL
          AND (a.consumida_em IS NOT NULL OR a.expira_em > now())
          AND (
              vc.numero = (SELECT MAX(u.numero) FROM versao_curriculo u WHERE u.vaga_id = vc.vaga_id)
              OR EXISTS (SELECT 1 FROM candidatura c WHERE c.versao_id = vc.id)
          )
    ) AS aprovada,
    EXISTS (SELECT 1 FROM candidatura c WHERE c.versao_id = vc.id) AS enviada
FROM versao_curriculo vc
WHERE vc.vaga_id IS NOT NULL;

COMMIT;
