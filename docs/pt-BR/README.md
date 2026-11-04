# grokbot-kit

> Read in English: [README.md](../../README.md)

Kit de integração Grok Bot: delega tarefas a agentes de código headless (opencode, Claude Code, Codex, DeepSeek
Harness) e acorda a routine do Grok Bot certo quando a tarefa termina ou precisa de uma permissão.

**Estado:** `0.x`. Os comandos abaixo funcionam; o schema de evento `grokbot-kit.event/v1` ainda pode mudar, sempre
com uma entrada no [CHANGELOG](../../CHANGELOG.md).

## O que é

Um Grok Bot que delega uma tarefa longa a um agente headless hiberna enquanto o agente roda, e nada o acorda. O
código de saída sozinho não diz se a tarefa foi feita, falhou ou parou num pedido de permissão.

O `grokbot-kit` embrulha a execução do agente (`grokbot-kit run`), escuta os hooks nativos de cada agente e envia
exatamente um evento terminal (`completed`, `error` ou `timeout`) - mais um `needs_input` quando o agente esbarra numa
permissão - ao webhook trigger da routine do bot que delegou. Os outros bots não são acordados.

## Instalação

```sh
uv tool install --managed-python grokbot-kit
```

`pipx install grokbot-kit` também funciona. Para testar o que está na `main` antes do release:

```sh
uv tool install --managed-python git+https://github.com/rodrigo-pasini/grokbot-kit
```

Requer Linux e Python 3.11 ou mais novo (o `uv` gerencia o interpretador). O pacote não tem dependências de runtime.

## Começo rápido

### Com um Grok Bot

Mande esta mensagem ao bot. Ele instala a [skill](#skill-do-grok-bot) e conduz o setup com você: o kit, as CLIs e o
login delas, a CLI padrão, os tiers de modelo e a routine que os eventos do bot acordam. Troque `meubot` por um nome
curto para o bot (letras, dígitos, `.`, `_` e `-`).

```text
Instale a skill grokbot-kit e faça o setup do grokbot-kit neste box:
1. Baixe https://github.com/rodrigo-pasini/grokbot-kit/releases/latest/download/SKILL.md (seguindo redirects)
   para /home/box/agent-data/workflows/grokbot-kit/SKILL.md (crie o diretório).
2. Leia essa skill e siga a seção "Setup (primeira vez)" do começo ao fim, um passo de cada vez,
   pulando o que o `grokbot-kit doctor --json` mostrar como já feito. Use "meubot" como nome deste bot.
3. Nunca me peça um segredo (API key, URL ou key da routine) no chat: leia você mesmo da routine
   ou me peça num campo mascarado de segredos, e passe pela entrada padrão do `grokbot-kit secret set`.
4. No fim, rode `grokbot-kit doctor --json` e resuma o resultado e os problemas.
```

O bot cria a routine, com webhook trigger e o prompt de routine da skill, ou pede que você a crie no painel do Grok
Bot. A URL e a key da routine ele lê sozinho ou pede uma a uma num campo mascarado de segredos, nunca no chat ou
num print. Com o setup pronto, peça uma tarefa pequena, como "renomeie as variáveis de x.py": o bot escolhe o tier `trivial`, avisa a
escolha, e o resultado chega pela routine.

<details>
<summary>Prints de um setup e de uma tarefa</summary>

**1. A mensagem e a escolha das CLIs**

![1. A mensagem e a escolha das CLIs](https://raw.githubusercontent.com/rodrigo-pasini/grokbot-kit/main/docs/images/quickstart/01-pedido-e-clis.png)

**2. opencode instalado, modelos gratuitos sem login**

![2. opencode instalado, modelos gratuitos sem login](https://raw.githubusercontent.com/rodrigo-pasini/grokbot-kit/main/docs/images/quickstart/02-login.png)

**3. Tiers de modelo e a routine criada pelo bot**

![3. Tiers de modelo e a routine criada pelo bot](https://raw.githubusercontent.com/rodrigo-pasini/grokbot-kit/main/docs/images/quickstart/03-tiers-e-routine.png)

**4. URL e key da routine pelo campo mascarado de segredos**

![4. URL e key da routine pelo campo mascarado de segredos](https://raw.githubusercontent.com/rodrigo-pasini/grokbot-kit/main/docs/images/quickstart/04-segredos.png)

**5. Uma tarefa delegada ao opencode, com o resultado de volta pela routine**

![5. Uma tarefa delegada ao opencode, com o resultado de volta pela routine](https://raw.githubusercontent.com/rodrigo-pasini/grokbot-kit/main/docs/images/quickstart/05-tarefa.png)

</details>

### À mão

```sh
grokbot-kit setup cli add opencode
grokbot-kit setup default opencode
grokbot-kit secret set meubot-url
grokbot-kit secret set meubot-key
grokbot-kit route add meubot --url-secret meubot-url --key-secret meubot-key
grokbot-kit route test meubot
grokbot-kit run --target meubot --label renomear-vars -- "Renomeie as variáveis de x.py"
```

O DeepSeek Harness é instalado com Node.js 24, sem instalador do kit; o kit detecta um `dsh` que já existe:

```sh
grokbot-kit setup cli add dsh
grokbot-kit login dsh --method api-key
grokbot-kit setup default dsh
grokbot-kit run --target meubot --label smoke -- "Responda exatamente: pong"
```

O perfil `headless` do `dsh` roda com `DSH_PERMISSION_MODE=danger-full-access` e usa por padrão o modelo Flash
(`deepseek-flash`, provedor `deepseek-official`). `--model` ainda registra o id pedido no evento, mas a v1 não
reescreve o perfil compartilhado em `~/.dsh` para trocar o modelo.

## Skill do Grok Bot

`skills/grokbot-kit/` é uma skill para qualquer Grok Bot. Copie a pasta para o diretório de workflows do bot e ele
consegue instalar o kit, instalar e logar nas CLIs que você escolher, criar a rota para a própria routine e delegar
tarefas escolhendo CLI e modelo.

## Comandos

| Comando | O que faz |
| --- | --- |
| `grokbot-kit run` | roda uma tarefa num agente headless e envia um evento terminal à rota de `--target`; o modelo vem de `--model` ou de `--tier` (`trivial`, `standard`, `complex`), e `--plugin` roda um [plugin](#plugins) |
| `grokbot-kit emit` | chamado pelos hooks dos agentes dentro de uma tarefa; não é para uso direto |
| `grokbot-kit redeliver <task_id>` | reenvia os eventos de uma tarefa que não foram entregues |
| `grokbot-kit gc --older-than <duração>` | remove os task dirs de tarefas que terminaram há muito tempo; `--dry-run` só lista |
| `grokbot-kit route add <bot>` | `add` liga um bot ao webhook da routine dele (URL e key de dois segredos), `rm` remove a rota, `test` envia um evento `test` |
| `grokbot-kit setup cli add <tool>` | configura as CLIs: `cli add` instala uma com o instalador oficial (`dsh` é detectado, não baixado), `default` escolhe a usada quando a tarefa não diz, `models refresh` descobre os ids de modelo, `providers` escolhe os provedores do opencode e `tiers` grava os ids de um tier (veja [Modelos](#modelos)) |
| `grokbot-kit login <tool>` | faz o login de uma CLI com o comando oficial dela, por assinatura ou API key (`--method`); o `dsh` usa API key e grava `$DSH_HOME/.env` |
| `grokbot-kit doctor` | confere versões, CLIs, logins, rotas, segredos e plugins, com o comando que corrige cada problema; `--json` para o bot |
| `grokbot-kit install opencode` | instala o plugin do opencode que avisa dos pedidos de permissão (inerte fora de uma tarefa) |
| `grokbot-kit uninstall opencode` | remove o plugin do opencode |
| `grokbot-kit update check` | diz se há versão nova; `apply` atualiza, `skip <versão>` e `later` param de perguntar |
| `grokbot-kit plugin list` | lista os plugins; `show` mostra um manifesto, `add` instala um de um diretório ou URL git, `rm` remove |
| `grokbot-kit secret set <nome>` | grava um segredo em `~/.secrets/grokbot-kit/` com modo `0600`, lido sem eco ou da entrada padrão |

`grokbot-kit <comando> --help` mostra todas as opções. As que não aparecem acima:

- `grokbot-kit --version` mostra a versão instalada.
- `run --tool <tool>` escolhe a CLI da tarefa (padrão: a gravada com `setup default`); `run --timeout <duração>`
  (`30m`, `2h`, `1d`) substitui o `timeouts.<tier>` do config; `run --prompt-file <arquivo>` lê o prompt de um arquivo,
  passado ao agente depois dos argumentos que seguem o `--`.
- `emit --from <tool>` diz de qual CLI é o hook que chama.
- `route add --header 'Nome: valor'` acrescenta um header a toda requisição da rota; repetível.
- `setup models refresh --add <id>` (`claude`, `codex` e `dsh`) também testa e grava um id que a descoberta não
  lista; no `dsh`, os ids conhecidos são a checagem leve.
- `login --secret <nome>` diz o segredo que guarda a API key (padrão: `<tool>-api-key`).

## Plugins

Um plugin é uma tarefa pronta: um prompt, as entradas que ele pede e o que o agente pode fazer enquanto roda (`write`,
`network`, `commands`). O kit traz o `code-review` (revisa um pull request do GitHub) e o `bug-verify`;
`grokbot-kit plugin list` mostra esses e os instalados. O bot roda um plugin com poucas entradas, sem escrever prompt,
e o evento traz o resultado estruturado do plugin:

```sh
grokbot-kit run --plugin code-review --input pr=https://github.com/<owner>/<repo>/pull/<n> --target <bot> --label review
```

O formato, as capacidades que cada CLI impõe e como escrever um plugin estão em [plugins.md](plugins.md).

## Modelos

`grokbot-kit setup models refresh --json` lista os ids de modelo de cada CLI. No opencode, cada id traz o provedor, o
texto antes do primeiro `/` (`opencode-go` em `opencode-go/<modelo>`). O bot pergunta quais provedores do opencode
você usa e grava a escolha; um provedor pago precisa antes de `grokbot-kit login opencode`:

```sh
grokbot-kit setup providers opencode opencode-go
```

Depois ele pergunta os ids de cada tier, em ordem. Com os provedores gravados, o `setup tiers` recusa um id do
opencode de outro provedor, e o `grokbot-kit doctor` acusa um tier que tenha um:

```sh
grokbot-kit setup tiers opencode standard <id> <id>
```

`grokbot-kit run --tier <tier>` lança o primeiro id do tier. Quando o provedor falha antes de o agente usar qualquer
ferramenta (opencode: um `error` sem `tool_use`; Claude Code: um `api_error` no primeiro turno), o kit lança o próximo
id na mesma tarefa, dentro do mesmo timeout. O evento diz em `model` o modelo que rodou por último e lista em
`model_fallbacks` os que falharam, com o motivo. Um modelo dado com `--model` nunca é trocado, e o Codex e o `dsh`
nunca tentam outro. Quando a tarefa falha sem mensagem final do agente, o `summary` traz o erro da CLI.

`setup cli add dsh` grava os ids conhecidos `deepseek-flash` e `deepseek-chat` e põe `deepseek-flash` nos três tiers,
então um setup novo roda Flash a menos que você escolha outro id. `grokbot-kit setup models refresh dsh` não chama
nenhum comando de modelos ao vivo. O perfil `headless` é a fonte do modelo real; para a v1, mantenha o Flash padrão.

## Evento

Cada evento que a routine recebe é um objeto JSON `grokbot-kit.event/v1`: `event` e `status` dizem como a tarefa
terminou, `summary` traz a mensagem final do agente e `resume_hint` o comando que retoma a sessão dele. Todos os campos
estão descritos em [event.md](event.md).

## Configuração

O config fica em `~/.config/grokbot-kit/config.toml`: CLIs instaladas e a padrão, tiers de modelo (`trivial`,
`standard`, `complex`) por CLI, timeout por tier e uma rota por bot. Cada task guarda saída, logs e eventos em
`~/.grokbot-kit/tasks/<task_id>/` até o `grokbot-kit gc` removê-la.

## Segurança

- Segredos (URL e key da routine, API keys) são gravados com `grokbot-kit secret set` em `~/.secrets/grokbot-kit/`
  com modo `0600`, nunca no config e nunca colados num chat.
- O `grokbot-kit` nunca escreve um segredo em log, stdout, stderr ou evento.
- `~/.claude/settings.json`, `~/.codex/` e `~/.dsh` nunca são modificados por uma tarefa; o Codex roda num
  `CODEX_HOME` próprio, e o `login dsh` só grava `DEEPSEEK_API_KEY` no `.env` do dsh com modo `0600`.

## Contribuindo

Veja [CONTRIBUTING.md](CONTRIBUTING.md).

## Licença

[MIT](../../LICENSE). Material de terceiros neste repositório está listado em [NOTICE](../../NOTICE).
