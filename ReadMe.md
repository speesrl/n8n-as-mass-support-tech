# N8N as our MAS support technology

## Quick Start

### Prima Installazione

Per la prima installazione, usa lo script di inizializzazione che configura automaticamente tutto:

```bash
cd n8n-as-mas-support-tech
./init-project.sh
```

Lo script `init-project.sh`:

- Chiede interattivamente le credenziali admin (email e password)
- Determina automaticamente UID/GID del tuo utente
- Crea tutte le directory necessarie
- Verifica e corregge i permessi
- Genera il file `.env` con tutte le configurazioni

Dopo l'inizializzazione:

```bash
# Avvia i container
podman compose up -d

# Attendi 30-60 secondi che i container siano pronti, poi inizializza N8N
./init-n8n.sh
```

Lo script `init-n8n.sh` crea automaticamente:

- Utente admin con le credenziali specificate in `.env`
- Progetto personale collegato all'utente
- Configurazione iniziale

**Nota:** Esegui `init-n8n.sh` dopo il primo `podman compose up -d` o se hai problemi di login.

### Installazioni Successive

Se hai già eseguito `init-project.sh` e hai il file `.env`:

```bash
# (Opzionale) Carica le variabili d'ambiente dal file .env
source .env

# Avvia i container
podman compose up -d

# Inizializza N8N (se necessario)
./init-n8n.sh
```

### Configurazione Manuale (Alternativa)

Se preferisci configurare manualmente invece di usare `init-project.sh`:

```bash
# Configura permessi e variabili d'ambiente
./setup_permissions.sh
export N8N_UID=$(id -u)
export N8N_GID=$(id -g)

# Poi avvia i container
podman compose up -d
```

Oppure aggiungi al tuo `~/.bashrc` o `~/.zshrc`:

```bash
export N8N_UID=$(id -u)
export N8N_GID=$(id -g)
```

Questo rende il setup più portabile e compatibile con il tuo utente.

## Script di Inizializzazione

### init-project.sh

Lo script `init-project.sh` prepara l'ambiente prima di eseguire `podman compose up -d`. Esegue automaticamente:

1. **Verifica prerequisiti**: Controlla che podman e docker-compose.yml siano presenti

2. **Configurazione credenziali admin**: Chiede interattivamente email e password per l'utente admin di N8N
   - Valida il formato email
   - Richiede password con conferma (minimo 6 caratteri)

3. **Determinazione UID/GID**: Rileva automaticamente l'UID e GID dell'utente corrente

4. **Creazione directory**: Crea tutte le directory `volumes/*` necessarie se mancanti

5. **Verifica permessi**: Controlla e corregge i permessi delle directory usando `podman unshare`

6. **Generazione file .env**: Crea il file `.env` con tutte le variabili d'ambiente:
   - `ADMIN_EMAIL` e `ADMIN_PASSWORD`: Credenziali admin
   - `N8N_UID` e `N8N_GID`: ID utente/gruppo per i container
   - `N8N_API_KEY`: Chiave API opzionale (vuota inizialmente)

Il file `.env` viene creato con permessi 600 (solo proprietario) per sicurezza.

**Utilizzo**:

```bash
./init-project.sh
```

Lo script è interattivo e guida l'utente attraverso il processo di configurazione.

### init-n8n.sh

Lo script `init-n8n.sh` crea l'utente admin e il progetto personale in N8N. Legge automaticamente le credenziali dal file `.env` se presente, altrimenti usa valori di default.

**Utilizzo**:

```bash
# Dopo che i container sono avviati e pronti
./init-n8n.sh
```

**Nota**: Esegui questo script dopo `podman compose up -d` e dopo aver atteso che i container siano completamente inizializzati (circa 30-60 secondi).

Servizi disponibili:

| Servizio | URL | Descrizione |
|----------|-----|-------------|
| **n8n** | http://localhost:5678 | Workflow automation |
| **MCP Server** | http://localhost:8012 | AI workflow generation |
| **RedisInsight** | http://localhost:9001 | Redis GUI |
| **Redis** | localhost:6389 | Cache/messaging |

## Credenziali di Accesso

Le credenziali admin sono configurate durante l'esecuzione di `init-project.sh` e salvate nel file `.env`:

- **Email:** Configurata durante `init-project.sh` (default: `admin@spee.it` se non specificato)
- **Password:** Configurata durante `init-project.sh` (default: `admin` se non specificato)

Il file `.env` contiene anche:

- `N8N_UID` e `N8N_GID`: ID utente/gruppo per i container
- `N8N_API_KEY`: Chiave API opzionale (può essere configurata dopo)

**Nota:** Il file `.env` è nel `.gitignore` e non viene committato nel repository per sicurezza.

## Struttura dei Volumi

Tutti i dati persistenti sono nella cartella `./volumes/`:

```text
volumes/
├── config/            # API key MCP
├── n8n_data/          # Configurazione n8n locale
├── postgres_data/     # Database PostgreSQL (utenti, workflow, credenziali)
├── redis_data/        # Dati Redis
├── redisinsight_data/ # Configurazione RedisInsight
└── workflows/         # Workflow esportati
```

I dati persistono tra `podman compose down` e `up`.

## Configurazione di Rete

Il docker-compose usa una rete custom con IP statici per la risoluzione DNS (compatibile con Podman CNI senza plugin aggiuntivi):

```text
| Container | IP | Hostname |
|-----------|-----|----------|
| n8n-db | 172.28.0.2 | db |
| n8n-redis | 172.28.0.3 | redis |
| n8n-redisinsight | 172.28.0.4 | redisinsight |
| n8n-app | 172.28.0.5 | n8n |
| n8n-mcp | 172.28.0.6 | n8n-mcp |
```

## MCP Server for N8N Workflow Generation

Il docker-compose include un MCP (Model Context Protocol) server che permette di generare workflow N8N tramite AI assistant come Cursor.

### Configurazione Cursor IDE

1. Apri Cursor IDE

2. Vai in: `File` > `Preferences` > `Settings` > `Tools & Integrations` > `MCP Tools`

3. Clicca su **Add MCP Server** e aggiungi:

```json
{
  "mcpServers": {
    "n8n": {
      "url": "http://localhost:8012/sse",
      "transport": "sse"
    }
  }
}
```

4. Riavvia Cursor

### Generare API Key N8N

1. Accedi a http://localhost:5678 con le credenziali dal file `.secret`

2. Vai in **Settings** > **API**

3. Clicca **Create API Key** e copia la chiave

4. In Cursor chat, salva la chiave:

   ```text
   Salva la N8N API Key: n8n_api_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

### Tool MCP Disponibili

- **save_api_key**: Salva API key nel volume persistente
- **generate_workflow**: Genera workflow JSON da requisiti
- **import_workflow**: Importa workflow in N8N
- **list_workflows**: Lista tutti i workflow
- **get_workflow**: Ottiene workflow per ID
- **list_saved_workflows**: Lista workflow salvati localmente

### Esempio di Utilizzo

In Cursor chat:

- "Genera un workflow N8N che ascolta un canale Redis e pubblica su un altro canale"
- "Lista tutti i workflow in N8N"
- "Importa questo workflow JSON in N8N"

## Script di Gestione Workflow

### Importare Workflow

Lo script `import_workflows.py` importa tutti i workflow dalla cartella `volumes/workflows/`:

```bash
# Importa tutti i workflow (salta quelli esistenti)
./import_workflows.py

# Aggiorna i workflow esistenti invece di skipparli
./import_workflows.py --update

# Specifica un URL N8N diverso
./import_workflows.py --url http://localhost:5678
```

### Eliminare Workflow

Lo script `delete_workflow.py` elimina un workflow dato il nome:

```bash
# Elimina un workflow (con conferma)
./delete_workflow.py "Nome Workflow"

# Elimina senza conferma
./delete_workflow.py "Nome Workflow" --force

# Specifica un URL N8N diverso
./delete_workflow.py "Nome Workflow" --url http://localhost:5678
```

**Nota**: Entrambi gli script usano automaticamente username/password dal file `.env` (se presente), oppure l'API key se disponibile.

### Reset Completo di N8N

Lo script `reset_n8n.sh` resetta N8N a uno stato vergine, eliminando tutti i dati persistenti:

```bash
# Reset completo (richiede conferma)
./reset_n8n.sh
```

**⚠️ ATTENZIONE**: Questo script elimina:

- Tutti i workflow salvati in N8N
- Tutti gli utenti e credenziali
- Tutti i dati del database PostgreSQL
- Tutti i dati di configurazione N8N
- Tutti i dati Redis

**I seguenti dati NON vengono eliminati**:

- Workflow esportati in `volumes/workflows/` (file JSON)
- Configurazione API key in `volumes/config/`

**Dopo il reset**, i container rimangono fermati. Devi:

1. Rigenerare la configurazione (se il file `.env` è stato eliminato):

   ```bash
   ./init-project.sh
   ```

   Oppure, se il file `.env` esiste ancora:

   ```bash
   source .env
   ```

2. Riavviare i container:

   ```bash
   podman compose up -d
   ```

3. Creare l'utente admin:

   ```bash
   ./init-n8n.sh
   ```

**Nota**: Le variabili `N8N_UID` e `N8N_GID` nel file `.env` permettono ai container di usare l'UID/GID del tuo utente invece di 1000:1000 hardcoded, rendendo il setup più portabile.

## Esempio Redis-Echo

In questo esempio un Redis trigger attende un messaggio sul canale A, un nodo Python lo elabora, e un altro nodo Redis lo pubblica sul canale B:

![N8N Redis-Echo example](n8n_basic.png)

Python code del nodo "Print":

```python
for item in _input.all():
  item.json.myNewField = 1
  output = item
  print(item)
return _input.all()
```

Nel campo `data` del nodo Redis per ri-pubblicare:

```json
{{ JSON.stringify($json.message) }}
```

## Configurazione Credenziali dopo Import Workflow

Quando importi un workflow, le credenziali non vengono incluse per motivi di sicurezza. Devi configurarle manualmente:

### Configurare Credenziali Redis

1. Apri il workflow importato in N8N UI (http://localhost:5678)

2. Clicca sul nodo Redis che mostra l'errore "credentials for Redis are not set"

3. Clicca su **"Create New Credential"** o seleziona una credenziale esistente

4. Configura i parametri:
   - **Host**: `redis` ⚠️ **IMPORTANTE**: Usa `redis` (non `n8n-redis`!)
     - Il container Redis ha `hostname: redis` nel docker-compose
     - I container sulla stessa rete Docker/Podman usano l'hostname per la risoluzione DNS
     - Se accedi da host (non da container), usa `localhost`
   - **Port**: `6379` ⚠️ **IMPORTANTE**: Usa `6379` (porta interna del container), NON `6389`!
     - La porta `6389` è solo per l'accesso dall'host (mappatura `6389:6379`)
     - Quando N8N (container) si connette a Redis (container), usa la porta interna `6379`
     - Se accedi da host, usa `6389` (porta mappata)
   - **Password**: (lascia vuoto se Redis non ha password configurata)
   - **Database**: `0` (default)

5. Salva la credenziale e il workflow dovrebbe funzionare

**Nota Importante**:

- **Da container N8N**: Usa `redis:6379` (hostname `redis`, porta interna `6379`)
  - ⚠️ **NON usare la porta 6389** - quella è solo per l'accesso dall'host!
- **Da host**: Usa `localhost:6389` (porta mappata `6389`)
- **NON usare** `n8n-redis` come hostname - quello è solo il `container_name`, non l'hostname per la risoluzione DNS!

**Configurazione corretta per N8N (container -> container)**:

- Host: `redis`
- Port: `6379` ← **Questa è la porta corretta!**

### Troubleshooting Connessione Redis

Se N8N non si connette a Redis nonostante la configurazione corretta:

1. **Verifica che Redis sia in esecuzione**:

   ```bash
   podman ps | grep redis
   podman exec n8n-redis redis-cli ping
   # Dovrebbe rispondere: PONG
   ```

2. **Verifica la connettività di rete dal container N8N**:

   ```bash
   podman exec n8n-app nc -zv redis 6379
   # Dovrebbe mostrare: redis (172.28.0.3:6379) open
   ```

3. **Verifica la risoluzione DNS**:

   ```bash
   podman exec n8n-app getent hosts redis
   # Dovrebbe mostrare: 172.28.0.3 redis
   ```

4. **Controlla la configurazione delle credenziali in N8N**:

   - Assicurati di aver salvato le credenziali dopo averle create
   - Verifica che il nodo Redis usi le credenziali corrette (clicca sul nodo e controlla il campo "Credential")
   - Prova a ricreare le credenziali se necessario

5. **Verifica la porta**:

   - ⚠️ **IMPORTANTE**: Usa porta `6379`, NON `6389`!
   - La porta `6389` è solo per l'accesso dall'host (vedi docker-compose.yml: `6389:6379`)
   - Quando N8N (container) si connette a Redis (container), deve usare la porta interna `6379`

6. **Se il problema persiste, prova con l'IP diretto**:

   - Host: `172.28.0.3`
   - Port: `6379` ← **Non 6389!**
   - (Questo bypassa la risoluzione DNS ma funziona come workaround)

## Troubleshooting

### Pagina bianca dopo login / "Could not find a personal project"

Se vedi una pagina bianca con errore nella console:

```text
ResponseError: Could not find a personal project for this user
```

Esegui lo script di inizializzazione:

```bash
./init-n8n.sh
```

Lo script verifica e crea automaticamente:

- L'utente admin se non esiste
- Il progetto personale se non esiste
- La relazione tra utente e progetto
- Le impostazioni utente necessarie

### Container non si connettono tra loro

Verifica che la rete abbia gli IP corretti:

```bash
podman network inspect n8n_n8n_net
```

### Reset completo

Per ricominciare da zero, usa lo script dedicato:

```bash
./reset_n8n.sh
```

Dopo il reset, rigenera la configurazione:

```bash
./init-project.sh
podman compose up -d
./init-n8n.sh
```

Oppure manualmente:

```bash
podman compose down
rm -rf volumes/postgres_data/*
rm -rf volumes/n8n_data/*
rm -rf volumes/redis_data/*
rm -rf volumes/redisinsight_data/*
./init-project.sh
podman compose up -d
./init-n8n.sh
```

**Nota**: Lo script `reset_n8n.sh` è più sicuro perché richiede conferma e preserva i workflow esportati. Il file `.env` non viene eliminato dal reset, ma puoi rigenerarlo con `init-project.sh` se necessario.
