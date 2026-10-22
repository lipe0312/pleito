BEGIN;

SET search_path TO pleito, public;

REVOKE SELECT ON SEQUENCE empresa_id_seq FROM pleito_app;

COMMIT;
