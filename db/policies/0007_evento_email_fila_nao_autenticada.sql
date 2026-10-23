BEGIN;

SET search_path TO pleito, public;

DROP POLICY IF EXISTS evento_cria ON evento_email;
CREATE POLICY evento_cria ON evento_email FOR INSERT TO pleito_app
    WITH CHECK (
        NOT aplicado
        AND (autenticado OR confianca < 1.0 OR fila IS NOT NULL)
        AND (tipo = 'suspeito') = (fila IS NOT DISTINCT FROM 'suspeito')
    );

COMMIT;
