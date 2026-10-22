BEGIN;

SET search_path TO pleito, public;

CREATE UNIQUE INDEX vaga_unica_por_conteudo
    ON vaga (fonte_id, COALESCE(empresa_id, 0), hash_conteudo);

INSERT INTO fonte (slug, nome, tipo, dominio, veredito) VALUES
    ('remotive', 'Remotive', 'agregador_api_publica', 'remotive.com', 'nao_testado'),
    ('arbeitnow', 'Arbeitnow', 'agregador_api_publica', 'www.arbeitnow.com', 'nao_testado'),
    ('himalayas', 'Himalayas', 'agregador_api_publica', 'himalayas.app', 'nao_testado'),
    ('remoteok', 'Remote OK', 'agregador_api_publica', 'remoteok.com', 'nao_testado'),
    ('jobicy', 'Jobicy', 'agregador_api_publica', 'jobicy.com', 'nao_testado'),
    ('weworkremotely', 'We Work Remotely', 'rss_remoto', 'weworkremotely.com', 'nao_testado'),
    ('jobspresso', 'Jobspresso', 'rss_remoto', 'jobspresso.co', 'nao_testado'),
    ('workingnomads', 'Working Nomads', 'agregador_api_publica', 'www.workingnomads.com', 'nao_testado'),
    ('hackernews', 'Hacker News', 'texto_livre', 'hn.algolia.com', 'nao_testado')
ON CONFLICT (slug) DO NOTHING;

COMMIT;
