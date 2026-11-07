# Termos de uso das fontes de vaga

Revisão feita em 2026-11-07 (F4.4, ameaça A4 em `docs/ameacas.md`). `robots.txt` não basta: cada
fonte teve a página pública de termos lida por GET sem login, só nos domínios de
`config/fontes.yaml` e na Gupy. O resultado vai para `termos` em `config/fontes.yaml`
(`revisado_em`, `veredito`, `link`) e o coletor recusa fonte sem `termos.revisado_em` ou com
veredito fora de `vereditos_coletaveis` (`permite`, `permite_com_condicao`).

Caso ambíguo vale como `proibe` até o Filipe decidir. Fonte com `proibe` fica com `ativa: false`,
sai da allowlist de domínios e não é coletada.

Uso do pleito para ler os vereditos: uso pessoal, não comercial, local, sem republicar vaga em
site nem repassar a terceiro.

| Fonte | Data | Link | Trecho que decide | Veredito |
| --- | --- | --- | --- | --- |
| `greenhouse` | 2026-11-07 | https://docs.greenhouse.io/job-board.html | "Job Board data is publicly available, so authentication is not required for any GET endpoints." Sem limite nem atribuição citados. robots: só `Disallow: /embed/`. | permite com condição: só GET públicos, rps de `.env`, robots |
| `lever` | 2026-11-07 | https://www.lever.co/legal/terms-of-service | Os termos são o contrato com empresas clientes e não tratam da leitura de vagas públicas; a documentação da API fica no GitHub, fora da allowlist, e não foi lida. robots de `api.lever.co`: `Allow: /`, `Crawl-delay: 1`. | permite com condição: respeitar o crawl-delay e rps de `.env` |
| `ashby` | 2026-11-07 | https://developers.ashbyhq.com/docs/public-job-posting-api | "This API allows you to get data for all currently published Job Postings for your organization." Sem limite nem atribuição citados. robots de `jobs.ashbyhq.com` bloqueia `/api/`, que não é o endpoint usado (`api.ashbyhq.com/posting-api`). | permite com condição: só o endpoint de posting-api |
| `remotive` | 2026-11-07 | https://remotive.com/remote-jobs/api | Termos do site: "Scrape, crawl, or use automated means to access the Site or extract data without our written permission". Termos da API: "Please link back to the URL found on Remotive AND mention Remotive as a source"; vagas atrasadas 24 h; proibido repassar a Jooble, Google Jobs, LinkedIn Jobs. | permite com condição: só `/api/remote-jobs`, nunca o HTML do site, atribuição, nada repassado |
| `arbeitnow` | 2026-11-07 | https://www.arbeitnow.com/terms | Termos: licença "for personal, non-commercial transitory viewing only"; proíbe uso comercial, exibição pública e espelhamento. O blog da API oferece "a free Job Board API". | permite com condição: uso pessoal e não comercial, sem exibir nem espelhar |
| `himalayas` | 2026-11-07 | https://himalayas.app/api | "Show the jobs only on sites and apps you operate. Do not pass them on to other job boards, aggregators, Google Jobs or LinkedIn Jobs"; "Use the applicationLink for every Apply button, unchanged"; "Show a visible link to the job on Himalayas"; 60 requisições por minuto. | permite com condição: atribuição, link de candidatura intacto, nada repassado |
| `remoteok` | 2026-11-07 | https://remoteok.com/legal | "You agree to link back with a web hyperlink or in-app hyperlink to our site on the page or app screen where you use the data from our APIs or site." O JSON da API repete: sem link e menção, o acesso é suspenso; logo só com permissão. | permite com condição: atribuição com link (`atribuicao_exigida: true`), sem logo |
| `jobicy` | 2026-11-07 | https://jobicy.com/terms-and-conditions | API: "Please credit Jobicy and link to the source"; "Polling a few times per day is normally sufficient and must not exceed once per hour"; vagas com 3 h de atraso. Termos do site: "Reproduction is prohibited other than in accordance with the copyright notice". | permite com condição: no máximo uma consulta por hora, crédito com link |
| `workingnomads` | 2026-11-07 | https://www.workingnomads.com/terms-and-conditions | Nenhuma cláusula sobre automação, raspagem ou extração. Proíbe revender ou explorar comercialmente o serviço. O endpoint `/api/exposed_jobs/` é público e o robots tem `Disallow:` vazio. | permite com condição: uso pessoal, sem revenda |
| `weworkremotely` | 2026-11-07 | https://weworkremotely.com/terms | Não foi possível ler: a página de termos responde 403 a GET sem login. Sem texto, não há como saber se o RSS pode ser coletado. robots libera o RSS. | proibe (ambíguo) |
| `jobspresso` | 2026-11-07 | https://jobspresso.co/terms-and-conditions/ | Licença "for personal, non-commercial transitory viewing only"; "modify or copy the materials" é vedado e não há cláusula sobre o feed. Gravar vagas no banco é cópia. robots libera o feed. | proibe (ambíguo) |
| `hackernews` | 2026-11-07 | https://hn.algolia.com/api | A página da API não traz termos, limite nem atribuição (só "Hacker News Search powered by Algolia"); os termos do Hacker News ficam em `ycombinator.com`, fora da allowlist. `robots.txt` responde 404. | proibe (ambíguo) |
| `solides` | 2026-11-07 | https://solides.com.br/termos-de-uso/ | Os termos cobrem o software de RH da Sólides, sem cláusula sobre listagem pública. 3.7(d): vedado "obter ou tentar obter qualquer material ou informação, por qualquer meio não disponibilizado ou não fornecido". 3.3 veda cópia de texto e conteúdo. A listagem também não traz dados no HTML inicial (SEM_DADOS). | proibe (ambíguo) |
| `linkedin_alertas` | 2026-11-07 | https://www.linkedin.com/legal/user-agreement | Página não lida de propósito: LinkedIn nunca é acessado. O pleito não toca o site; só lê o email de alerta que o próprio Filipe recebe no Gmail. | permite com condição: só email de alerta, site nunca automatizado |
| `gupy` (fora de `config/fontes.yaml`) | 2026-11-07 | https://portal.gupy.io/termos-de-uso | A URL responde 200 mas serve a página inicial do portal, sem termos; os avisos de privacidade em `gupy.io` tratam de dados pessoais e não de coleta de vagas. Sem texto de uso automatizado. robots de `portal.gupy.io`: `Disallow:` vazio. | proibe (ambíguo): a coleta fica para F4.7, depois da decisão do Filipe |

## Escolha: fontes que saíram da coleta

`weworkremotely`, `jobspresso`, `hackernews` e `solides` ficaram `proibe` por falta de texto
legível ou por cláusula que pode valer para cópia. Para reabrir uma delas, o Filipe lê a página,
confirma e muda `termos.veredito` e `ativa` em `config/fontes.yaml`; nenhum código muda.
Hacker News e Gupy valem uma consulta ao suporte ou leitura dos termos fora do alcance do
agente.
