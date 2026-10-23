BEGIN;

SET search_path TO pleito, public;

GRANT INSERT (fila) ON evento_email TO pleito_app;

DROP POLICY IF EXISTS evento_cria ON evento_email;
CREATE POLICY evento_cria ON evento_email FOR INSERT TO pleito_app
    WITH CHECK (NOT aplicado AND (autenticado OR confianca < 1.0 OR fila = 'suspeito'));

DROP POLICY IF EXISTS evento_aplica ON evento_email;
CREATE POLICY evento_aplica ON evento_email FOR UPDATE TO pleito_app
    USING (NOT aplicado AND fila IS NULL)
    WITH CHECK (aplicado AND autenticado AND fila IS NULL);

COMMIT;
