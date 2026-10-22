BEGIN;

SET search_path TO pleito, public;

GRANT INSERT (nome) ON empresa TO pleito_app;
GRANT USAGE, SELECT ON SEQUENCE empresa_id_seq TO pleito_app;

COMMIT;
