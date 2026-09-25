CREATE SCHEMA IF NOT EXISTS pleito;

CREATE TABLE IF NOT EXISTS pleito.migracao (
    arquivo     text PRIMARY KEY,
    sha256      text NOT NULL,
    aplicada_em timestamptz NOT NULL DEFAULT now()
);
