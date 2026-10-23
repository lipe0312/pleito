BEGIN;

SET search_path TO pleito, public;

ALTER TYPE estado_vaga ADD VALUE IF NOT EXISTS 'oferta' AFTER 'teste';

ALTER TABLE evento_email
    ADD COLUMN fila text,
    ADD CONSTRAINT evento_fila_valida CHECK (fila IS NULL OR fila IN ('classificar', 'suspeito')),
    ADD CONSTRAINT evento_aplicado_fora_da_fila CHECK (NOT (aplicado AND fila IS NOT NULL));

CREATE INDEX evento_email_fila_idx ON evento_email (fila) WHERE fila IS NOT NULL;

COMMIT;
