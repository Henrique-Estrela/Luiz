# Luiz

Assistente pessoal por voz com wake word, comandos automatizados e resposta inteligente.

Agora com modo de resposta em ensemble (GPT + Gemini) com economia de custo:

- Politica `adaptive` (padrao): usa 1 LLM na maioria das mensagens e ativa o segundo apenas em pedidos complexos.
- Sem terceira chamada de sintese: o segundo LLM atua como revisor, reduzindo custo por interacao.
- Cache em memoria para repeticoes no mesmo processo.

E agora com energia diaria de tokens:

- Ao passar de 70% da cota diaria, o Luiz avisa que a energia esta acabando.
- Ao chegar em 95%, o Luiz avisa que vai descansar e entra em modo sono.
- O modo sono dura ate a virada da cota diaria (reset automatico por dia).

Estado atual (V1 funcional):

- Escuta continua no microfone.
- So ativa quando ouve "Luiz".
- Recebe comando por voz.
- Executa tools basicas (abrir site, rodar script, chamar API, criar arquivo).
- Responde por texto no terminal e por voz no sistema.

## Arquitetura Implementada

- `run.py`: bootstrap da execucao.
- `src/luiz/app.py`: loop principal de voz e orquestracao.
- `src/luiz/audio/`: captura de audio, STT e TTS.
- `src/luiz/agent/brain.py`: decisao do agente e fallback para LLM.
- `src/luiz/agent/tools.py`: catalogo de tools executaveis.
- `scripts/`: scripts locais permitidos para execucao.

## Requisitos

- Windows 10/11
- Python 3.11+ (recomendado 3.12)
- Microfone configurado

## Instalacao

1. Criar e ativar ambiente virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Instalar dependencias:

```powershell
pip install -r requirements.txt
```

3. Configurar variaveis de ambiente:

```powershell
Copy-Item .env.example .env
```

4. Editar `.env` e preencher pelo menos uma chave LLM:

- `OPENAI_API_KEY`
- `GEMINI_API_KEY`

Para modo combinado, preencha as duas.

## Execucao

```powershell
python run.py
```

Ao iniciar, o Luiz fica em escuta continua e apenas responde quando detectar a palavra de chamada.

## Comandos de Voz Disponiveis

- Abrir site:
	- "Luiz" -> "abra site github.com"
- Rodar script local:
	- "Luiz" -> "rode script exemplo.py"
- Chamar API:
	- "Luiz" -> "chamar api https://api.github.com"
- Criar arquivo:
	- "Luiz" -> "criar arquivo notas.txt conteudo: lembrar de revisar o projeto"
- Encerrar:
	- "Luiz" -> "encerrar"

## Ajustes Finos no .env

- `LUIZ_WAKE_WORDS`: variacoes aceitas para chamada.
- `LUIZ_OPENAI_MODEL`: modelo OpenAI usado pelo Luiz.
- `LUIZ_GEMINI_MODEL`: modelo Gemini usado pelo Luiz.
- `LUIZ_PRIMARY_LLM`: define o lado primario (`openai` ou `gemini`).
- `LUIZ_DUAL_POLICY`:
	- `adaptive` (recomendado): segundo LLM so em casos complexos.
	- `single`: usa apenas o primario (menor custo).
	- `always`: usa os dois sempre (maior custo).
- `LUIZ_DAILY_TOKEN_BUDGET`: orcamento diario de tokens somando GPT e Gemini.
- `LUIZ_QUOTA_WARNING_RATIO`: percentual para aviso de energia baixa (padrao 0.70).
- `LUIZ_QUOTA_SLEEP_RATIO`: percentual para entrar em descanso (padrao 0.95).
- `LUIZ_QUOTA_STATE_FILE`: arquivo local que guarda o consumo diario.
- `LUIZ_STT_MODEL`: `tiny`, `base`, `small` (maior = mais preciso, mais lento).
- `LUIZ_INPUT_SECONDS`: janela de escuta da wake word.
- `LUIZ_COMMAND_SECONDS`: janela para comando apos ativacao.
- `LUIZ_ENERGY_THRESHOLD`: sensibilidade de captacao de audio.

## Observacoes Importantes

- Sem as duas chaves, o Luiz continua funcionando nas tools, mas respostas abertas ficam em modo degradado.
- Com as duas chaves ativas e politica `adaptive`, a reducao tipica de custo fica proxima de 70% comparado ao modo de dupla chamada sempre com sintese extra.
- Durante o descanso por cota (95%), o Luiz nao processa novas solicitacoes de comando ate o proximo dia.
- A execucao de script e limitada a pasta `scripts` para reduzir risco.
- Se o microfone nao for detectado, verifique permissao de privacidade do Windows para apps desktop.
