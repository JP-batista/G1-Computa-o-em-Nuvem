# Sistema de mensagens distribuído com Docker

Três containers Python (Flask) que recebem mensagens por uma API REST, replicam cada mensagem entre si e guardam tudo em um volume compartilhado. Projeto da Avaliação de Grau 1 de Computação em Nuvem.

## Arquitetura

```
 host:5001 -> app1 --+
 host:5002 -> app2 --+--  rede bridge "msgnet"
 host:5003 -> app3 --+
                     |
                     v
        volume "mensagens" montado em /data
        (app1.log, app2.log, app3.log)
```

- `app1`, `app2` e `app3` usam a mesma imagem (`msg-app`) e mudam apenas por variáveis de ambiente.
- Entre si, os containers se falam pelo nome do serviço, sempre na porta interna 5000 (por exemplo `http://app2:5000`). As portas 5001, 5002 e 5003 existem só para acesso de fora, a partir do host.
- Cada instância grava em um arquivo próprio dentro do volume compartilhado.

## Estrutura de arquivos

```
.
├── app/
│   ├── app.py             # serviço Flask
│   ├── requirements.txt   # flask e requests
│   ├── Dockerfile         # imagem da aplicação
├── docker-compose.yml     # 3 serviços, volume e rede bridge
├── test.sh                # teste de ponta a ponta
└── README.md
```

## Como executar

Pré-requisitos: Docker com Docker Compose.

```bash
docker compose up -d --build   # sobe os 3 containers
docker compose ps              # confere o status
docker compose down            # para e remove (o volume é mantido)
docker compose down -v         # também apaga o volume com as mensagens
```

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| POST | `/send` | Recebe `{"message": "texto"}`, grava localmente e envia uma cópia aos outros dois containers. Responde 201, com o resultado da replicação de cada peer. Sem o campo `message`, responde 400. |
| GET | `/messages` | Retorna as mensagens do arquivo da própria instância. |
| POST | `/replicate` | Rota interna, usada entre os containers. Só grava, não reenvia. |
| GET | `/verify` | Compara os IDs deste log com os dos outros e informa se estão sincronizados. |

Cada mensagem é uma linha JSON no log, com `id` (UUID), `origin` (instância que recebeu o `/send`), `message` e `ts` (timestamp).

## Como testar

### Automático

```bash
bash test.sh
```

O script sobe os containers, envia uma mensagem pelo `app1`, confere que ela chegou nas três portas, lista os logs do volume e consulta o `/verify`. Termina com "todos os testes passaram" ou indica o que falhou.

### Manual

Linux/macOS/Git Bash:

```bash
curl -X POST -H "Content-Type: application/json" -d '{"message":"hello"}' http://localhost:5001/send
curl http://localhost:5002/messages
curl http://localhost:5001/verify
docker compose exec app1 ls /data
```

PowerShell:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:5001/send -ContentType "application/json" -Body '{"message":"hello"}'
Invoke-RestMethod http://localhost:5002/messages
Invoke-RestMethod http://localhost:5001/verify
```

## Decisões de projeto

- **Um arquivo de log por instância** (`app1.log`, `app2.log`, `app3.log`). Se os três escrevessem no mesmo arquivo, cada mensagem apareceria duplicada (a gravação local mais as cópias recebidas).
- **`/replicate` separada de `/send`.** A cópia recebida é só gravada. Se ela fosse reenviada, as mensagens circulariam entre os containers indefinidamente.
- **`id` único por mensagem (UUID).** Permite comparar o conteúdo dos logs entre as instâncias sem depender da ordem ou do horário.
- **`/verify` lê os logs dos outros no volume.** Como o volume é compartilhado, um container consegue comparar seu arquivo com o dos demais.
- **Falha de um peer não derruba o `/send`.** A replicação usa timeout de 3 s e captura erros. O resultado de cada peer volta na resposta (`ok` ou `falhou: ...`).
- **Dockerfile enxuto.** Imagem `python:3.12-slim`, `requirements.txt` copiado antes do código (aproveita o cache de camadas), `pip install --no-cache-dir`, só `flask` e `requests`, e `EXPOSE 5000`.
- **Configuração por variáveis de ambiente** (`INSTANCE_NAME`, `PEERS`, `DATA_DIR`), o que permite usar a mesma imagem nas três instâncias.

## Resultados dos testes

- Mensagem enviada ao `app1` aparece em `app1`, `app2` e `app3`, e o mesmo vale ao enviar pelo `app3`.
- `/verify` retorna `in_sync: true` para todos os peers.
- Com o `app2` parado, o `/send` continua respondendo: `app2` aparece como falha e `app3` como `ok`. O `/verify` mostra o `app2` fora de sincronia.
- Após `docker compose down` e `up`, as mensagens continuam disponíveis, porque ficam no volume.

## Limitações

- Não há retry nem reconciliação: um container que esteve fora do ar não recebe depois as mensagens que perdeu. O `/verify` apenas detecta a diferença.
- Escritas simultâneas no mesmo arquivo não usam lock. Em uso real, seria preciso um banco ou uma fila.
- O servidor embutido do Flask é de desenvolvimento. Em produção, usaria gunicorn.
- Não há autenticação, e `/replicate` aceita chamadas de qualquer cliente que alcance a porta.
