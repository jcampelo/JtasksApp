# Revisao tecnica: endurecimento de sessao e cookies

Data da analise: 2026-04-24

Projeto: JtasksApp

Status: documento para avaliacao tecnica. Nenhuma mudanca de codigo foi executada por este documento.

## 1. Resumo executivo

O JtasksApp usa Supabase Auth para login e guarda informacoes da sessao do usuario com o `SessionMiddleware` do Starlette.

O ponto de atencao e que o projeto descreve a sessao como "server-side session", mas o middleware atual salva o conteudo da sessao em um cookie assinado no navegador. Esse cookie e protegido contra adulteracao, mas nao e criptografado. Hoje, o conteudo salvo na sessao inclui `access_token` e `refresh_token` do Supabase.

Em termos simples: o navegador esta carregando uma copia das chaves temporarias usadas para acessar a conta do usuario. O servidor consegue perceber se alguem alterou o cookie, mas o modelo atual nao deve ser tratado como armazenamento secreto server-side.

A melhoria recomendada e mover os tokens sensiveis para um armazenamento no servidor e deixar no navegador apenas um identificador opaco de sessao, como `session_id`.

## 2. Explicacao para contexto nao especializado

Quando um usuario faz login, o Supabase entrega ao app dois tipos principais de credencial:

- `access_token`: uma chave temporaria usada para acessar os dados do usuario.
- `refresh_token`: uma chave usada para renovar o acesso quando o `access_token` expira.

Esses tokens funcionam como passes de acesso. Se forem expostos, podem permitir que alguem acesse recursos em nome do usuario enquanto forem validos.

O app precisa guardar esses tokens em algum lugar para continuar fazendo chamadas ao Supabase depois que o usuario ja fez login. Hoje eles ficam dentro da sessao do Starlette.

O detalhe importante: no `SessionMiddleware` padrao do Starlette, a sessao nao fica armazenada no servidor. Ela fica em um cookie no navegador, assinada com uma chave secreta. A assinatura impede que o usuario altere o cookie sem ser detectado, mas nao transforma o conteudo em um segredo protegido no servidor.

Uma analogia util:

- Cookie assinado: parecido com um envelope lacrado. Se alguem mexer, o servidor percebe.
- Cookie criptografado ou sessao server-side: parecido com guardar o conteudo em um cofre e entregar ao navegador apenas um numero de protocolo.

Para tokens de autenticacao, o modelo mais seguro e o segundo: o navegador guarda apenas um identificador sem valor direto, e o servidor guarda as credenciais reais.

## 3. Evidencias encontradas no codigo

### 3.1 Middleware de sessao atual

Arquivo: `main.py`

Trecho relevante:

```python
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, https_only=False)
```

Observacoes:

- O projeto usa `SessionMiddleware` do Starlette.
- `https_only=False` esta fixo.
- Em producao com HTTPS, o ideal e que cookies de sessao sejam enviados apenas por conexoes seguras.

### 3.2 Tokens Supabase salvos na sessao

Arquivo: `app/routers/auth.py`

Trecho relevante:

```python
request.session["user"] = {
    "access_token": session_data.access_token,
    "refresh_token": session_data.refresh_token,
    "expires_at": session_data.expires_at,
    "user_id": str(user.id),
    "email": user.email,
}
```

Observacoes:

- O `access_token` e o `refresh_token` sao colocados diretamente na sessao.
- Como a sessao atual e baseada em cookie assinado, esses dados acabam indo para o navegador.

### 3.3 Renovacao do token tambem atualiza a sessao

Arquivo: `app/deps.py`

Trecho relevante:

```python
result = client.auth.refresh_session(session["refresh_token"])
session["access_token"] = result.session.access_token
session["refresh_token"] = result.session.refresh_token
session["expires_at"] = result.session.expires_at
request.session["user"] = session
```

Observacoes:

- Quando o token e renovado, os novos tokens tambem sao salvos na sessao.
- No modelo atual, isso significa que o cookie pode carregar tokens atualizados ao longo do tempo.

### 3.4 Documentacao sugere sessao server-side

Arquivo: `README.md`

Trecho relevante:

```text
Supabase Auth (server-side session)
```

Observacao:

- A documentacao diz que a sessao e server-side.
- O comportamento atual do `SessionMiddleware` nao corresponde exatamente a isso, porque o conteudo da sessao e serializado no cookie.

## 4. Risco pratico

Este ponto nao significa que o app esteja automaticamente vulneravel para qualquer visitante. O cookie de sessao normalmente tem protecoes importantes, como `HttpOnly`, e a assinatura impede adulteracao.

Mesmo assim, para um sistema com dados corporativos, multiusuario, permissoes e integracao com Supabase, e uma decisao arriscada manter tokens sensiveis dentro de um cookie armazenado no navegador.

Riscos principais:

- Se um cookie de sessao for copiado, pode levar junto tokens do Supabase.
- O `refresh_token` e especialmente sensivel, porque permite renovar acesso.
- A configuracao atual usa `https_only=False`, entao falta uma barreira importante para ambiente de producao.
- A documentacao pode induzir manutencao futura incorreta, pois chama o modelo atual de server-side.

## 5. Estado desejado

O estado desejado e:

1. O navegador guarda apenas um cookie com um identificador opaco, por exemplo `session_id`.
2. Esse `session_id` nao contem `access_token`, `refresh_token`, email ou dados sensiveis.
3. Os tokens Supabase ficam guardados no servidor ou em um armazenamento controlado pelo servidor.
4. Em cada request protegida, o servidor usa o `session_id` para buscar a sessao real.
5. Se o token estiver perto de expirar, o servidor renova com o Supabase e atualiza o armazenamento server-side.
6. No logout, o servidor remove/invalida a sessao server-side e limpa o cookie.
7. Em producao, o cookie deve usar `Secure`, `HttpOnly` e `SameSite` apropriado.

## 6. Alternativas tecnicas

### Alternativa A: apenas endurecer cookie e documentacao

Mudancas:

- Adicionar configuracao `SESSION_HTTPS_ONLY`.
- Usar `https_only=True` em producao.
- Ajustar `same_site`, nome do cookie e documentacao.
- Manter tokens dentro da sessao atual.

Vantagens:

- Menor esforco.
- Baixo risco de regressao.
- Melhora a postura em producao.

Desvantagens:

- Nao resolve o problema principal: os tokens continuam no cookie.
- A sessao ainda nao seria server-side de verdade.

Conclusao:

- Boa melhoria rapida, mas incompleta.

### Alternativa B: sessao server-side usando tabela no Supabase

Mudancas:

- Criar tabela de sessoes, por exemplo `app_sessions`.
- O cookie passa a guardar apenas um `session_id`.
- A tabela guarda `user_id`, `email`, `access_token`, `refresh_token`, `expires_at`, datas de criacao/atualizacao e eventual data de revogacao.
- O app usa `get_service_client()` somente dentro de um servico central de sessoes.
- Opcionalmente, criptografar os tokens antes de salvar na tabela.

Vantagens:

- Evita adicionar nova infraestrutura na VPS.
- Aproveita Supabase, que o projeto ja usa.
- Facilita revogar sessoes e auditar logins.
- Resolve o principal problema: tokens deixam de ir para o navegador.

Desvantagens:

- Exige migracao de banco.
- Exige cuidado para nao espalhar uso de `service_key` fora do servico de sessoes.
- Se os tokens forem salvos sem criptografia em repouso, ainda existe risco caso a tabela seja exposta por erro operacional.

Conclusao:

- Boa opcao pragmatica para este projeto, principalmente se a equipe quiser evitar Redis ou outro servico novo.

### Alternativa C: sessao server-side usando Redis

Mudancas:

- Adicionar Redis na VPS.
- O cookie guarda apenas `session_id`.
- Os tokens ficam no Redis com TTL.
- Logout remove a chave do Redis.

Vantagens:

- Modelo classico para sessao server-side.
- TTL e expiracao sao naturais.
- Bom desempenho.

Desvantagens:

- Adiciona nova dependencia operacional.
- Exige configurar, monitorar e proteger Redis.
- Pode ser excesso para uma aplicacao pequena se a VPS ainda nao usa Redis.

Conclusao:

- Tecnicamente forte, mas talvez aumente a complexidade operacional mais do que o necessario neste momento.

## 7. Recomendacao inicial

Recomendo que o senior avalie a Alternativa B como caminho principal:

- Manter Supabase como armazenamento de sessoes.
- Criar um servico dedicado, por exemplo `app/services/session_service.py`.
- Guardar no cookie apenas um `session_id` opaco.
- Centralizar toda leitura, renovacao e revogacao de sessao nesse servico.
- Adicionar configuracao para cookie seguro por ambiente.
- Atualizar README e CLAUDE.md para refletir o modelo real.

Se a empresa ja tiver Redis ou preferir padrao de mercado para sessoes, a Alternativa C tambem e adequada.

Nao recomendo ficar apenas na Alternativa A como solucao final, porque ela endurece o cookie mas nao corrige o desenho central.

## 8. Desenho proposto de fluxo

### 8.1 Login

Fluxo atual:

1. Usuario informa email e senha.
2. App chama Supabase Auth.
3. Supabase retorna tokens.
4. App grava tokens em `request.session`.
5. Cookie de sessao e enviado ao navegador.

Fluxo proposto:

1. Usuario informa email e senha.
2. App chama Supabase Auth.
3. Supabase retorna tokens.
4. App cria um `session_id` aleatorio e forte.
5. App salva os tokens no armazenamento server-side.
6. App envia ao navegador apenas o cookie com `session_id`.

### 8.2 Request autenticada

Fluxo proposto:

1. Navegador envia cookie com `session_id`.
2. App busca a sessao correspondente no armazenamento server-side.
3. App monta o contexto do usuario com `user_id`, `email`, `access_token`, `refresh_token` e `expires_at`.
4. Se o token estiver perto de expirar, app renova no Supabase.
5. App atualiza o armazenamento server-side com os novos tokens.
6. Router segue usando `get_user_client(...)` como hoje.

### 8.3 Logout

Fluxo proposto:

1. Usuario clica em sair.
2. App remove ou revoga a sessao server-side.
3. App limpa o cookie do navegador.
4. O mesmo `session_id` nao deve funcionar novamente.

## 9. Arquivos provaveis envolvidos em uma implementacao futura

Arquivos que provavelmente seriam alterados:

- `main.py`: configuracao de cookie/middleware ou substituicao do modelo de sessao.
- `app/config.py`: novas variaveis de configuracao, como ambiente, cookie seguro e chave de criptografia se aplicavel.
- `app/routers/auth.py`: login e logout passariam a criar/remover sessao server-side.
- `app/deps.py`: `get_current_user()` passaria a resolver `session_id` em vez de ler tokens diretamente do cookie.
- `app/services/session_service.py`: novo servico central para criar, buscar, renovar e revogar sessoes.
- `migrations/...`: nova migracao se a opcao escolhida usar tabela no Supabase.
- `.env.example`: documentar novas variaveis.
- `README.md` e `CLAUDE.md`: corrigir a descricao do modelo de sessao.
- `tests/...`: testes de regressao para cookie, login, logout, expiracao e ausencia de tokens no cookie.

## 10. Cuidados de seguranca na implementacao

Pontos que devem ser garantidos:

- Gerar `session_id` com fonte criptograficamente segura.
- Nao colocar `access_token` nem `refresh_token` no cookie.
- Usar cookie `HttpOnly`.
- Usar cookie `Secure` em producao.
- Definir `SameSite`, provavelmente `lax`, salvo necessidade especifica.
- Rotacionar ou invalidar sessao no logout.
- Remover sessoes expiradas periodicamente.
- Evitar uso espalhado de `get_service_client()` nos routers.
- Se os tokens forem salvos em banco, avaliar criptografia em repouso no nivel da aplicacao.
- Nao quebrar o fluxo local em `http://127.0.0.1:8080`.

## 11. Plano de teste local antes de qualquer Git/CI

Este projeto tem CI ativo no Git. Portanto, a ordem correta deve ser:

1. Implementar localmente.
2. Rodar testes automatizados:

```powershell
.\.venv\Scripts\pytest
```

3. Subir a aplicacao localmente:

```powershell
.\.venv\Scripts\uvicorn main:app --port 8080 --reload
```

4. Acessar:

```text
http://127.0.0.1:8080
```

5. Testar manualmente:

- Login com usuario aprovado.
- Logout.
- Tentativa de acessar `/app` sem login.
- Acesso as abas principais.
- Criacao/listagem de tarefas.
- Funcionalidades que usam `get_user_client`.
- Feature de monitoring/permissoes, se disponivel para o usuario de teste.
- Renovacao de sessao, se for possivel simular token proximo de expirar.

6. Verificar cookie no navegador:

- O cookie nao deve conter `access_token`.
- O cookie nao deve conter `refresh_token`.
- O cookie deve conter apenas identificador opaco.
- Em ambiente local, `Secure` pode ficar desativado para funcionar em HTTP.
- Em producao, `Secure` deve estar ativado.

7. So depois dos testes locais, preparar commit.

8. So depois de aprovacao explicita, fazer push para o Git remoto, onde o CI sera executado.

## 12. Criterios de aceite

Uma implementacao futura pode ser considerada concluida quando:

- Nenhum cookie contem `access_token` ou `refresh_token`.
- Login continua funcionando.
- Logout invalida a sessao.
- Usuarios nao autenticados nao acessam rotas protegidas.
- Renovacao de token continua funcionando.
- Rotas existentes continuam recebendo `user["user_id"]`, `user["email"]`, `user["access_token"]` e `user["refresh_token"]` ou uma interface equivalente.
- Testes automatizados passam localmente.
- Teste manual local passa antes de qualquer push.
- Documentacao deixa claro onde a sessao fica armazenada.
- Cookie fica com `Secure` em producao e sem `Secure` apenas no ambiente local.

## 13. Possivel estrategia de migracao

Para reduzir risco:

1. Criar o novo servico de sessao sem remover de imediato todo o fluxo antigo.
2. Alterar login para criar nova sessao server-side.
3. Alterar `get_current_user()` para primeiro tentar novo cookie de `session_id`.
4. Se o cookie antigo existir, considerar forcar novo login em vez de tentar migrar silenciosamente.
5. Usar nome de cookie novo, por exemplo `jtasks_session`, para evitar ambiguidade com o cookie atual `session`.
6. Fazer deploy em janela controlada, aceitando que usuarios precisem logar novamente.

Essa abordagem e simples e evita carregar tokens antigos do cookie para dentro do novo modelo.

## 14. Estrategia de rollback

Caso a alteracao cause problema em producao:

- Reverter o commit da nova sessao.
- Restaurar o fluxo antigo temporariamente.
- Manter a tabela de sessoes criada, se existir, sem uso imediato.
- Usuarios podem precisar logar novamente.

Como a mudanca afeta autenticacao, rollback deve ser previsto antes do deploy.

## 15. Perguntas para avaliacao do senior

1. A empresa prefere evitar nova infraestrutura e usar uma tabela no Supabase, ou aceita adicionar Redis?
2. Os tokens devem ser criptografados em repouso no armazenamento server-side?
3. Qual deve ser a duracao maxima de uma sessao?
4. Deve existir revogacao de todas as sessoes de um usuario?
5. O app precisa permitir multiplos dispositivos logados ao mesmo tempo?
6. A empresa quer manter compatibilidade com sessoes atuais ou pode exigir novo login apos deploy?
7. Existe proxy/Nginx garantindo redirecionamento HTTP para HTTPS em producao?
8. O CI atual cobre autenticacao ou sera necessario ampliar testes?

## 16. Como retomar este raciocinio depois

Ao voltar para esta melhoria, usar este documento como ponto de partida e pedir:

```text
Vamos implementar a proposta de endurecimento de sessao descrita em docs/session-security-hardening-review.md.
Primeiro revise o documento e proponha um plano local de implementacao e teste. Nao faca push sem minha autorizacao.
```

Antes de implementar, a decisao principal que ainda precisa ser tomada e o armazenamento da sessao:

- Supabase table: mais alinhado ao stack atual.
- Redis: mais classico para sessao, mas adiciona operacao.
- Apenas cookie seguro: melhoria parcial, nao recomendada como solucao final.

