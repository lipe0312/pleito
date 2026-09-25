\set app_password `echo "$POSTGRES_APP_PASSWORD"`

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pleito_app_login') THEN
        CREATE ROLE pleito_app_login LOGIN IN ROLE pleito_app;
    END IF;
END
$$;

ALTER ROLE pleito_app_login WITH PASSWORD :'app_password';
ALTER ROLE pleito_app_login SET search_path TO pleito, public;
