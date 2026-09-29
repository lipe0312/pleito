# Política de privacidade do pleito

Última atualização: 2026-09-29.

O pleito é uma ferramenta pessoal e local, feita e usada por uma única pessoa, seu autor, para
organizar a própria busca de estágio e emprego. Não é um serviço público, não tem outros usuários
e não é oferecido a terceiros. Código-fonte: https://github.com/lipe0312/pleito

## Dados acessados

Com autorização do próprio autor, por OAuth, o pleito acessa a caixa do Gmail dele para:

- ler mensagens ligadas a candidaturas e vagas;
- aplicar e remover rótulos `Candidaturas/*` e arquivar essas mensagens;
- enviar um email de resumo diário ao próprio autor.

O escopo solicitado é `https://www.googleapis.com/auth/gmail.modify`.

## Onde os dados ficam

Todo o processamento ocorre no computador do autor. Dados de email e credenciais ficam em um banco
local e no Keychain do macOS. Nada é enviado a servidores do projeto, porque não existem
servidores do projeto.

## Compartilhamento

Dados do Gmail não são vendidos, divulgados nem usados para publicidade. Quando o autor habilitar
a classificação de mensagens ambíguas, trechos podem ser enviados à API da OpenAI, sob os termos
e a política de dados dela. Fora isso, não há compartilhamento com terceiros.

## Uso limitado

O uso e a transferência de informações recebidas das APIs do Google seguem a Política de Dados do
Usuário dos Serviços de API do Google, inclusive os requisitos de Uso Limitado. Os dados são
usados somente para as funções descritas acima.

## Retenção e exclusão

Os dados ficam no computador do autor pelo tempo definido na configuração do projeto. O acesso
pode ser revogado a qualquer momento em https://myaccount.google.com/permissions, e os dados
locais podem ser apagados removendo o banco e o Keychain.

## Contato

Pelas issues do repositório: https://github.com/lipe0312/pleito/issues

---

# Privacy policy (English summary)

pleito is a personal, local-only tool built and used by a single person, its author, to manage his
own job search. It has no other users. With the author's OAuth consent it reads his Gmail, applies
`Candidaturas/*` labels, archives job-related messages and sends a daily summary email to himself
(scope `gmail.modify`). All processing happens on the author's own computer; there are no project
servers. Gmail data is not sold, shared or used for advertising. If the author enables message
classification, excerpts may be sent to the OpenAI API under its terms. Use of information
received from Google APIs adheres to the Google API Services User Data Policy, including the
Limited Use requirements. Access can be revoked at https://myaccount.google.com/permissions.
Contact: https://github.com/lipe0312/pleito/issues
