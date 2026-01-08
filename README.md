# Milano Express - Pricing Bot

Bot Telegram per monitoraggio prezzi Airbnb e suggerimenti dinamici per Milano Express B&B.

## 🎯 Funzionalità

- ✅ Monitoraggio prezzi competitor Airbnb
- ✅ Algoritmo pricing dinamico basato su:
  - Eventi importanti (Olimpiadi, Salone Mobile, Fashion Week)
  - Stagionalità
  - Giorno della settimana
  - Media mercato competitor
- ✅ Suggerimenti "prova e abbassa" automatici
- ✅ Notifiche giornaliere e settimanali su Telegram
- ✅ Comandi interattivi per analisi prezzi

## 📋 Prerequisiti

- Account Telegram
- Account Render.com (FREE tier)
- Bot Telegram creato con @BotFather

## 🚀 Setup Completo - Guida Passo-Passo

### FASE 1: Telegram Bot (✅ COMPLETATO)

- ✅ Bot creato: `@milano_express_pricing_bot`
- ✅ Token: `8289525063:AAEUYllkaQqilrOQiEHcrLmgO5AS5Ig4HtU`
- ✅ Gruppo creato: "Milano Express - Pricing"
- ✅ Group Chat ID: `-5263037342`
- ✅ Bot reso amministratore gruppo

### FASE 2: Database PostgreSQL su Render

1. **Vai su** https://render.com/dashboard
2. **New +** → **PostgreSQL**
3. **Configurazione:**
   - Name: `milano-express-pricing-db`
   - Database: `pricing_db`
   - User: `pricing_user`
   - Region: `Frankfurt (EU Central)`
   - Plan: **FREE**
4. **Create Database**
5. **Copia "Internal Database URL"** dalla pagina del database

### FASE 3: Deploy su Render

1. **Crea account GitHub** (se non ce l'hai)
2. **Crea nuovo repository** chiamato `milano-pricing-bot`
3. **Carica questi file** nel repository:
   - `bot.py`
   - `requirements.txt`
   - `README.md`

4. **Torna su Render.com**
5. **New +** → **Web Service**
6. **Collega il repository GitHub** appena creato
7. **Configurazione:**
   - Name: `milano-pricing-bot`
   - Region: `Frankfurt`
   - Branch: `main`
   - Runtime: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python bot.py`
   - Plan: **FREE**

8. **Environment Variables** (clicca "Advanced"):
   ```
   BOT_TOKEN = 8289525063:AAEUYllkaQqilrOQiEHcrLmgO5AS5Ig4HtU
   GROUP_CHAT_ID = -5263037342
   DATABASE_URL = [INCOLLA QUI L'URL DEL DATABASE POSTGRESQL]
   ```

9. **Create Web Service**

### FASE 4: Test e Verifica

1. **Aspetta deploy** (2-3 minuti)
2. **Nel gruppo Telegram**, invia: `/start`
3. **Testa comandi:**
   - `/oggi` - Prezzo suggerito oggi
   - `/domani` - Previsione domani
   - `/settimana` - Trend 7 giorni
   - `/eventi` - Eventi prossimi
   - `/help` - Lista comandi

## 🤖 Comandi Disponibili

| Comando | Descrizione |
|---------|-------------|
| `/start` | Avvia il bot e mostra benvenuto |
| `/oggi` | Analisi e prezzo suggerito per oggi |
| `/domani` | Previsione prezzo domani |
| `/settimana` | Trend prezzi prossimi 7 giorni |
| `/eventi` | Lista eventi impattanti (Olimpiadi, Salone, ecc.) |
| `/competitor` | Prezzi competitor (in sviluppo) |
| `/help` | Lista completa comandi |

## 💰 Logica Pricing

### Prezzi Base
- **Settimana (Lun-Gio):** €42/notte
- **Weekend (Ven-Sab):** €55/notte
- **Limiti:** Min €35, Max €150

### Eventi 2026 con Impatto Prezzi

| Evento | Date | Moltiplicatore | Prezzo Stimato |
|--------|------|----------------|----------------|
| **Olimpiadi Invernali** | 6-22 Feb | x2.8 | €120-140 |
| **Salone del Mobile** | 21-26 Apr | x2.3 | €90-110 |
| **Fashion Week** | Gen/Giu | x1.4 | €60-70 |
| **Paralimpiadi** | 6-15 Mar | x2.0 | €80-95 |
| **TUTTOFOOD** | 11-14 Mag | x1.4 | €60-70 |

### Fattori Considerati
1. **Eventi** (peso 40%) - Olimpiadi, Salone Mobile, Fashion Week
2. **Stagionalità** (peso 15%) - Estate +20%, Inverno -5%
3. **Giorno settimana** (peso 10%) - Weekend +15%, Domenica -5%
4. **Media mercato** (peso 30%) - Prezzi competitor zona Seveso
5. **Preavviso** (peso 5%) - Last minute +10-15%

## 📊 Sistema "Prova e Abbassa"

Il bot suggerisce prezzi progressivamente più bassi se non ricevi prenotazioni:

```
T+0h:  Prezzo iniziale suggerito: €55
T+48h: Nessuna prenotazione → Abbassa a €50 (-9%)
T+96h: Ancora libero → Abbassa a €45 (-18%)
```

**Limiti:**
- Mai sotto €35 (anche con abbassamenti)
- Sistema si attiva solo per date senza prenotazioni

## 🗓️ Notifiche Automatiche

### Report Giornaliero (ore 7:00)
- Prezzo suggerito per oggi
- Eventi nelle prossime 48h
- Reminder abbassamento prezzi (se applicabile)

### Report Settimanale (Lunedì ore 8:00)
- Trend prezzi settimana
- Eventi importanti in arrivo
- Statistiche prenotazioni

### Alert Eventi (24h prima)
- "Olimpiadi tra 1 giorno - Alza prezzo!"
- "Salone del Mobile domani - Verifica disponibilità"

## 🛡️ Protezioni Anti-Ban Airbnb

- ✅ User-Agent rotation automatica
- ✅ Delay randomizzati 10-18 secondi
- ✅ Max 5 competitor monitorati
- ✅ Scraping notturno (ore 3-5 AM)
- ✅ Limite richieste giornaliere

## 📁 Struttura Database

### Tabelle
- `competitors` - Lista competitor Airbnb
- `price_history` - Storico prezzi scraped
- `events` - Eventi 2026 con impatto
- `pricing_suggestions` - Prezzi suggeriti giornalieri
- `price_adjustments` - Log abbassamenti progressivi

## 🔧 Manutenzione

### Aggiungere nuovo competitor
```sql
INSERT INTO competitors (name, airbnb_id, url) 
VALUES ('Nome B&B', 'ID_AIRBNB', 'https://airbnb.it/rooms/...');
```

### Aggiungere nuovo evento
```sql
INSERT INTO events (name, start_date, end_date, category, impact_score, multiplier)
VALUES ('Nome Evento', '2026-XX-XX', '2026-XX-XX', 'fiera', 8, 1.5);
```

### Modificare prezzi base
Edita le costanti in `bot.py`:
```python
PRICES_CONFIG = {
    'BASE_WEEKDAY': 42,
    'BASE_WEEKEND': 55,
    'MIN_PRICE': 35,
    'MAX_PRICE': 150,
}
```

## 🐛 Troubleshooting

### Bot non risponde
1. Verifica che il servizio su Render sia "Active"
2. Controlla i logs su Render Dashboard
3. Verifica variabili ambiente (BOT_TOKEN, GROUP_CHAT_ID)

### Database errore
1. Verifica che DATABASE_URL sia corretto
2. Controlla che il database PostgreSQL sia attivo su Render
3. Controlla i logs per errori di connessione

### Scraping non funziona
**NOTA:** Lo scraping Airbnb è difficile perché Airbnb blocca bot.
Alternative:
- Usare servizio API a pagamento (AirDNA, Mashvisor)
- Inserire prezzi manualmente
- Usare proxy residenziali

## 📈 Roadmap Futuri Sviluppi

- [ ] Integrazione API AirDNA per prezzi mercato
- [ ] Machine learning su storico prenotazioni
- [ ] Integrazione calendario Airbnb (via API ufficiale)
- [ ] Grafici visuali prezzi (matplotlib/plotly)
- [ ] Export Excel report mensili
- [ ] Notifiche push anomalie mercato

## 💡 Supporto

Per domande o problemi, contatta il gruppo Telegram "Milano Express - Pricing"

---

**Sviluppato per Milano Express B&B** 🏠🇮🇹
Seveso, Milano - Corso Borromeo 17
