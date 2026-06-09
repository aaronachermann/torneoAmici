# Gestione Torneo di Hockey

Un'applicazione web per la gestione completa di un torneo di hockey, sviluppata con Flask.
In locale usa SQLite; in produzione usa PostgreSQL quando e configurata `DATABASE_URL`.

## Caratteristiche

- Gestione squadre e giocatori
- Controllo tesseramento giocatori con sistema di punti
- Generazione automatica del calendario delle partite
- Gestione dei risultati e statistiche
- Classifiche per gironi e playoff
- Statistiche individuali dei giocatori

## Requisiti

- Python 3.8 o superiore
- Pacchetti Python elencati in `requirements.txt`

## Installazione

1. Clona il repository o scarica i file

2. Crea un ambiente virtuale (opzionale ma consigliato):

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. Configura le variabili d'ambiente minime:

```bash
export SECRET_KEY="cambia-questa-chiave"
export ADMIN_USERNAME="admin"
export ADMIN_PASSWORD="scegli-una-password-sicura"
```

Se avvii l'app con `gunicorn` o su Railway e vuoi creare automaticamente le tabelle al boot:

```bash
export AUTO_INIT_DB="1"
```

4. Avvia l'applicazione:

```bash
python app.py
```

## Primo utilizzo

1. Avvia l'applicazione
2. Apri il browser e vai a `http://127.0.0.1:5000`
3. Accedi con l'utente admin configurato nelle variabili d'ambiente
4. Aggiungi le 16 squadre (4 per ogni girone)
5. Per ogni squadra, aggiungi i giocatori e specifica il loro tesseramento
6. Genera i gironi e il calendario delle partite
7. Inserisci i risultati delle partite man mano che vengono disputate
8. Visualizza le classifiche e le statistiche

## Deploy gratis con Render + Supabase

Questa configurazione evita SQLite online, perche sui servizi free il filesystem puo essere temporaneo.

### 1. Crea il database su Supabase

1. Crea un progetto su Supabase.
2. Clicca Connect e scegli la connection string PostgreSQL.
3. Per Render usa la stringa Session pooler, di solito sulla porta `5432` con host `pooler.supabase.com`.
4. Aggiungi `?sslmode=require` alla fine se non e gia presente.

Esempio:

```text
postgresql://postgres.xxxxx:password@aws-0-eu-central-1.pooler.supabase.com:5432/postgres?sslmode=require
```

### 2. Pubblica il progetto su GitHub

Render legge il codice da GitHub/GitLab/Bitbucket. Assicurati di non pubblicare file locali come:

- `.env`
- `instance/tournament.db`
- `venv/`

Sono gia esclusi da `.gitignore`.

### 3. Crea il Web Service su Render

Opzione consigliata: usa `render.yaml` presente nel repository.

In alternativa configura manualmente:

```text
Runtime: Python
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app --bind 0.0.0.0:$PORT
Plan: Free
```

### 4. Variabili ambiente su Render

Imposta queste variabili in Environment:

```text
DATABASE_URL=postgresql://...supabase.../postgres?sslmode=require
SECRET_KEY=una-chiave-lunga-casuale
ADMIN_USERNAME=admin
ADMIN_PASSWORD=una-password-sicura
AUTO_INIT_DB=1
PYTHON_VERSION=3.11.11
```

`AUTO_INIT_DB=1` crea le tabelle e l'admin al boot. Se l'admin esiste gia, non lo ricrea.

### 5. Primo accesso online

1. Apri l'URL `https://nome-servizio.onrender.com`.
2. Accedi con `ADMIN_USERNAME` e `ADMIN_PASSWORD`.
3. Configura squadre, giocatori e calendario.

Nota: il piano free di Render va in sleep dopo inattivita; il primo caricamento dopo una pausa puo richiedere circa un minuto.
