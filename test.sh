#!/usr/bin/env bash
# Teste de ponta a ponta do sistema de mensagens distribuído.
# Uso: ./test.sh   (precisa de docker compose e curl)

set -u

MSG="teste-$(date +%s)"
FALHAS=0

ok()   { echo "  [OK]   $1"; }
erro() { echo "  [ERRO] $1"; FALHAS=$((FALHAS + 1)); }

echo "1) Subindo os containers..."
docker compose up -d --build || { echo "Falha ao subir o compose"; exit 1; }

echo "2) Aguardando as 3 instâncias responderem..."
for porta in 5001 5002 5003; do
  for i in $(seq 1 20); do
    curl -s -o /dev/null "http://localhost:$porta/messages" && break
    sleep 1
  done
done

echo "3) Enviando a mensagem '$MSG' pelo app1 (porta 5001)..."
RESP=$(curl -s -X POST -H "Content-Type: application/json" \
  -d "{\"message\":\"$MSG\"}" http://localhost:5001/send)
echo "$RESP" | grep -q '"app2": *"ok"' && ok "replicou para app2" || erro "replicação para app2"
echo "$RESP" | grep -q '"app3": *"ok"' && ok "replicou para app3" || erro "replicação para app3"

echo "4) Conferindo a mensagem em cada instância..."
for porta in 5001 5002 5003; do
  curl -s "http://localhost:$porta/messages" | grep -q "$MSG" \
    && ok "porta $porta tem a mensagem" || erro "porta $porta NÃO tem a mensagem"
done

echo "5) Conferindo os logs no volume compartilhado..."
docker compose exec -T app1 ls /data

echo "6) Verificando sincronização (/verify)..."
curl -s http://localhost:5001/verify | grep -q '"in_sync": *false' \
  && erro "há instâncias fora de sincronia" || ok "todas as instâncias em sincronia"

echo
if [ "$FALHAS" -eq 0 ]; then
  echo "RESULTADO: todos os testes passaram."
else
  echo "RESULTADO: $FALHAS teste(s) falharam."
  exit 1
fi
