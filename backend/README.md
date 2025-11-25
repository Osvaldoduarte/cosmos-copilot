# 🚀 Backend - Copilot de Vendas

## ⚡ Quick Start

### Desenvolvimento (Agora)

```bash
# 1. Inicie o ngrok (em um terminal)
ngrok http 8000

# 2. Configure o webhook (em outro terminal)
cd backend
source .venv/bin/activate
python configure_ngrok_webhook.py

# 3. Teste enviando uma mensagem do WhatsApp!
```

### Produção (Deploy no Cloud Run)

```bash
# 1. Edite deploy_cloudrun.sh (linha 9)
PROJECT_ID="seu-projeto-id"

# 2. Execute o deploy
./deploy_cloudrun.sh

# 3. Configure o webhook
python configure_production_webhook.py
```

## 📚 Documentação

- **[Resumo da Solução](file:///Users/osvaldoduarte/.gemini/antigravity/brain/9fadc0eb-82f5-4cb9-b0d7-a96f2df8dba3/resumo_solucao.md)** - Visão geral completa
- **[Guia de Deploy](file:///Users/osvaldoduarte/.gemini/antigravity/brain/9fadc0eb-82f5-4cb9-b0d7-a96f2df8dba3/deploy_cloudrun_guide.md)** - Deploy no Cloud Run
- **[Problema do Webhook](file:///Users/osvaldoduarte/.gemini/antigravity/brain/9fadc0eb-82f5-4cb9-b0d7-a96f2df8dba3/problema_webhook.md)** - Explicação detalhada

## 🛠️ Scripts Úteis

| Script | Descrição |
|--------|-----------|
| `configure_ngrok_webhook.py` | Configura webhook com ngrok |
| `configure_production_webhook.py` | Configura webhook em produção |
| `check_webhook.py` | Verifica configuração atual |
| `test_integration.py` | Teste completo do fluxo |
| `deploy_cloudrun.sh` | Deploy automatizado |

## 🧪 Testes

```bash
# Teste o webhook
python test_webhook.py

# Teste integração completa
python test_integration.py

# Monitore WebSocket
python monitor_websocket.py

# Verifique configuração
python check_webhook.py
```

## 📝 Status Atual

✅ Webhook configurado com ngrok  
✅ Pronto para testes de desenvolvimento  
📦 Pronto para deploy em produção  

## 🆘 Problemas?

1. **Mensagens não chegam:** Verifique se ngrok está rodando
2. **Webhook não configura:** Execute `python check_webhook.py`
3. **Erros no deploy:** Veja logs com `gcloud run services logs read`
