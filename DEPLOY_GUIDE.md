# 🚀 GUIDA DEPLOY RENDER - PASSO PASSO

## ✅ PREREQUISITI COMPLETATI

- ✅ Bot Telegram: `@milano_express_pricing_bot`
- ✅ Token: `8289525063:AAEUYllkaQqilrOQiEHcrLmgO5AS5Ig4HtU`
- ✅ Group Chat ID: `-5263037342`
- ✅ Codice pronto

---

## 📋 FASE 1: CREA DATABASE POSTGRESQL

### Step 1.1: Accedi a Render
1. Vai su: https://render.com/dashboard
2. Login con il tuo account

### Step 1.2: Crea Database
1. Clicca **"New +"** (in alto a destra)
2. Seleziona **"PostgreSQL"**

### Step 1.3: Configurazione Database
```
Name: milano-express-pricing-db
Database: pricing_db
User: pricing_user
Region: Frankfurt (EU Central)
PostgreSQL Version: 16 (lascia default)
```

### Step 1.4: Piano FREE
- Seleziona: **"Free"** (0$/month)
- Storage: 1GB (sufficiente)
- Clicca **"Create Database"**

### Step 1.5: Aspetta Creazione
⏳ Aspetta ~2 minuti mentre Render crea il database

### Step 1.6: Copia Database URL
📋 **IMPORTANTE!** Quando pronto:
1. Nella pagina del database, scorri fino a **"Connections"**
2. **Copia "Internal Database URL"**
   
   Sarà tipo:
   ```
   postgresql://pricing_user:abc123xyz...@dpg-xxxxx-frankfurt-postgres.render.com/pricing_db
   ```

3. **SALVALA in un file di testo!** Ti serve dopo.

---

## 📁 FASE 2: CARICA CODICE SU GITHUB

### Step 2.1: Crea Repository GitHub
1. Vai su: https://github.com/new
2. **Repository name**: `milano-pricing-bot`
3. **Description**: "Bot prezzi dinamici Milano Express B&B"
4. **Public** o **Private** (a tua scelta)
5. **NON** aggiungere README (già incluso)
6. Clicca **"Create repository"**

### Step 2.2: Carica i File
Hai due opzioni:

**OPZIONE A - Upload Web (più facile):**
1. Nella pagina del repo, clicca **"uploading an existing file"**
2. **Trascina questi file** che ti ho preparato:
   - `bot.py`
   - `requirements.txt`
   - `README.md`
   - `.gitignore`
3. Commit message: "Initial commit"
4. Clicca **"Commit changes"**

**OPZIONE B - Git CLI:**
```bash
# Se hai git installato
git clone https://github.com/TUO_USERNAME/milano-pricing-bot.git
cd milano-pricing-bot
# Copia i file che ti ho preparato nella cartella
git add .
git commit -m "Initial commit"
git push
```

✅ Repository pronto!

---

## 🌐 FASE 3: DEPLOY SU RENDER

### Step 3.1: Crea Web Service
1. Torna su Render Dashboard: https://render.com/dashboard
2. Clicca **"New +"** → **"Web Service"**

### Step 3.2: Connetti GitHub
1. Clicca **"Connect account"** (se prima volta)
2. Autorizza Render ad accedere a GitHub
3. **Seleziona il repository**: `milano-pricing-bot`
4. Clicca **"Connect"**

### Step 3.3: Configurazione Service
```
Name: milano-pricing-bot
Region: Frankfurt (EU Central)
Branch: main
Runtime: Python 3
```

### Step 3.4: Build & Start Commands
```
Build Command:
pip install -r requirements.txt

Start Command:
python bot.py
```

### Step 3.5: Piano FREE
- Instance Type: **"Free"** (0$/month)
- ⚠️ NOTA: Il servizio FREE va in sleep dopo 15 min inattività
  ma si risveglia automaticamente al primo messaggio

### Step 3.6: Environment Variables
**IMPORTANTE!** Clicca **"Advanced"** e aggiungi queste variabili:

```
BOT_TOKEN = 8289525063:AAEUYllkaQqilrOQiEHcrLmgO5AS5Ig4HtU
GROUP_CHAT_ID = -5263037342
DATABASE_URL = [INCOLLA QUI L'URL DEL DATABASE CHE HAI COPIATO PRIMA]
```

📋 Esempio DATABASE_URL:
```
postgresql://pricing_user:abc123xyz...@dpg-xxxxx-frankfurt-postgres.render.com/pricing_db
```

### Step 3.7: Deploy!
1. Clicca **"Create Web Service"**
2. ⏳ Aspetta deploy (2-3 minuti)

### Step 3.8: Verifica Logs
- Durante il deploy, vedrai i logs in tempo reale
- Cerca questi messaggi positivi:
  ```
  ✅ "Database schema initialized"
  ✅ "Initial data loaded"
  ✅ "Bot started successfully!"
  ```

---

## ✅ FASE 4: TEST BOT

### Step 4.1: Primo Test
1. **Apri Telegram**
2. **Vai nel gruppo** "Milano Express - Pricing"
3. **Invia**: `/start`

### Step 4.2: Verifica Risposta
Dovresti ricevere:
```
🏠 Milano Express - Pricing Bot

Bot per monitoraggio prezzi Airbnb e suggerimenti dinamici.

Comandi disponibili:
/oggi - Analisi mercato oggi
/domani - Previsione domani
...
```

### Step 4.3: Testa Comandi
Prova questi comandi:

```
/oggi       → Dovresti vedere il prezzo suggerito per oggi
/domani     → Previsione domani
/settimana  → Trend 7 giorni con prezzi
/eventi     → Lista Olimpiadi, Salone, ecc.
/help       → Lista completa comandi
```

---

## 🎉 COMPLETATO!

Se tutti i comandi rispondono correttamente:
✅ Bot funzionante
✅ Database connesso
✅ Eventi 2026 caricati
✅ Algoritmo pricing attivo

---

## 🔧 TROUBLESHOOTING

### ❌ Bot non risponde
**Causa**: Service su Render in sleep o errore

**Soluzione:**
1. Vai su Render Dashboard
2. Apri il service "milano-pricing-bot"
3. Controlla che sia **"Live"** (pallino verde)
4. Guarda i **"Logs"** per errori
5. Se vedi errori, mandameli!

### ❌ Errore database
**Causa**: DATABASE_URL sbagliato

**Soluzione:**
1. Vai al service su Render
2. **Environment** → verifica `DATABASE_URL`
3. Copia di nuovo l'URL dal database PostgreSQL
4. Aggiorna la variabile
5. Clicca **"Save Changes"** (restart automatico)

### ❌ Comandi rispondono ma senza dati
**Causa**: Schema database non inizializzato

**Soluzione:**
1. Guarda i logs su Render
2. Cerca "Database schema initialized"
3. Se manca, c'è un errore di connessione DB
4. Verifica DATABASE_URL

---

## 📝 PROSSIMI PASSI

Dopo il deploy:

1. **Testa tutti i comandi** nel gruppo
2. **Verifica eventi 2026** con `/eventi`
3. **Controlla prezzi suggeriti** con `/settimana`
4. **Attendi notifiche automatiche**:
   - Report giornaliero: ore 7:00
   - Report settimanale: Lunedì ore 8:00

---

## 🆘 SERVE AIUTO?

Se qualcosa non funziona:
1. Copia i **logs da Render** (tab Logs)
2. Fai screenshot dell'errore
3. Mandameli e ti aiuto a risolvere!

---

**Pronto per il deploy? Segui gli step sopra!** 🚀
