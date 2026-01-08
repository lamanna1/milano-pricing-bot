#!/usr/bin/env python3
"""
Milano Express - Pricing Bot
Bot Telegram per monitoraggio prezzi Airbnb e suggerimenti dinamici
"""

import os
import logging
import asyncio
from datetime import datetime, timedelta, date
from decimal import Decimal
import json
from typing import Optional, List, Dict, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
import requests
from bs4 import BeautifulSoup
import random
import time

# Configurazione logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configurazione da variabili ambiente
BOT_TOKEN = os.environ.get('BOT_TOKEN')
GROUP_CHAT_ID = int(os.environ.get('GROUP_CHAT_ID'))
DATABASE_URL = os.environ.get('DATABASE_URL')

# Configurazione prezzi
PRICES_CONFIG = {
    'BASE_WEEKDAY': 42,      # Lun-Gio
    'BASE_WEEKEND': 55,      # Ven-Sab
    'MIN_PRICE': 35,         # Mai sotto
    'MAX_PRICE': 150,        # Mai sopra
    'WEEKEND_MULTIPLIER': 1.15,
    'SUNDAY_DISCOUNT': 0.95,
}

# Eventi 2026 hardcoded
EVENTS_2026 = [
    {
        'name': 'Olimpiadi Invernali Milano-Cortina',
        'start': '2026-02-06',
        'end': '2026-02-22',
        'impact': 10,
        'multiplier': 2.8,
        'category': 'olimpiadi'
    },
    {
        'name': 'Paralimpiadi Invernali',
        'start': '2026-03-06',
        'end': '2026-03-15',
        'impact': 8,
        'multiplier': 2.0,
        'category': 'paralimpiadi'
    },
    {
        'name': 'Salone del Mobile Milano',
        'start': '2026-04-21',
        'end': '2026-04-26',
        'impact': 10,
        'multiplier': 2.3,
        'category': 'fiera'
    },
    {
        'name': 'Milano Fashion Week Uomo FW',
        'start': '2026-01-16',
        'end': '2026-01-20',
        'impact': 7,
        'multiplier': 1.4,
        'category': 'moda'
    },
    {
        'name': 'Milano Fashion Week Uomo SS',
        'start': '2026-06-19',
        'end': '2026-06-23',
        'impact': 7,
        'multiplier': 1.4,
        'category': 'moda'
    },
    {
        'name': 'HOMI Milano',
        'start': '2026-01-22',
        'end': '2026-01-25',
        'impact': 5,
        'multiplier': 1.2,
        'category': 'fiera'
    },
    {
        'name': 'MICAM Milano',
        'start': '2026-02-22',
        'end': '2026-02-24',
        'impact': 6,
        'multiplier': 1.3,
        'category': 'fiera'
    },
    {
        'name': 'LINEAPELLE',
        'start': '2026-02-11',
        'end': '2026-02-13',
        'impact': 5,
        'multiplier': 1.2,
        'category': 'fiera'
    },
    {
        'name': 'TUTTOFOOD',
        'start': '2026-05-11',
        'end': '2026-05-14',
        'impact': 6,
        'multiplier': 1.4,
        'category': 'fiera'
    },
]

# Competitor URLs
COMPETITORS = [
    {
        'name': 'Competitor 1',
        'airbnb_id': '1160107109343011290',
        'url': 'https://www.airbnb.it/rooms/1160107109343011290'
    },
    {
        'name': 'Competitor 2',
        'airbnb_id': '845070499530356430',
        'url': 'https://www.airbnb.it/rooms/845070499530356430'
    },
    {
        'name': 'Competitor 3',
        'airbnb_id': '1315093379066044987',
        'url': 'https://www.airbnb.it/rooms/1315093379066044987'
    },
    {
        'name': 'Competitor 4',
        'airbnb_id': '890625863311377711',
        'url': 'https://www.airbnb.it/rooms/890625863311377711'
    },
    {
        'name': 'Competitor 5',
        'airbnb_id': '1180138186052044350',
        'url': 'https://www.airbnb.it/rooms/1180138186052044350'
    },
]


class Database:
    """Gestione database PostgreSQL"""
    
    def __init__(self, url: str):
        self.url = url
        self.conn = None
        
    def connect(self):
        """Connessione al database"""
        if not self.conn or self.conn.closed:
            self.conn = psycopg2.connect(self.url)
        return self.conn
    
    def execute(self, query: str, params: tuple = None, fetch: bool = False):
        """Esegui query"""
        conn = self.connect()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            if fetch:
                return cur.fetchall()
            conn.commit()
    
    def init_schema(self):
        """Inizializza schema database"""
        schema = """
        CREATE TABLE IF NOT EXISTS competitors (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            airbnb_id TEXT UNIQUE NOT NULL,
            url TEXT NOT NULL,
            active BOOLEAN DEFAULT true,
            created_at TIMESTAMP DEFAULT NOW()
        );
        
        CREATE TABLE IF NOT EXISTS price_history (
            id SERIAL PRIMARY KEY,
            competitor_id INTEGER REFERENCES competitors(id),
            date DATE NOT NULL,
            price DECIMAL(10,2),
            available BOOLEAN DEFAULT true,
            scraped_at TIMESTAMP DEFAULT NOW()
        );
        
        CREATE TABLE IF NOT EXISTS events (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            category TEXT,
            impact_score INTEGER,
            multiplier DECIMAL(5,2),
            created_at TIMESTAMP DEFAULT NOW()
        );
        
        CREATE TABLE IF NOT EXISTS pricing_suggestions (
            id SERIAL PRIMARY KEY,
            date DATE UNIQUE NOT NULL,
            suggested_price DECIMAL(10,2) NOT NULL,
            base_price DECIMAL(10,2),
            market_avg DECIMAL(10,2),
            event_multiplier DECIMAL(5,2),
            event_name TEXT,
            reasoning JSONB,
            confidence DECIMAL(5,2),
            applied BOOLEAN DEFAULT false,
            created_at TIMESTAMP DEFAULT NOW()
        );
        
        CREATE TABLE IF NOT EXISTS price_adjustments (
            id SERIAL PRIMARY KEY,
            date DATE NOT NULL,
            original_price DECIMAL(10,2) NOT NULL,
            adjusted_price DECIMAL(10,2) NOT NULL,
            adjustment_reason TEXT,
            hours_elapsed INTEGER,
            created_at TIMESTAMP DEFAULT NOW()
        );
        
        CREATE INDEX IF NOT EXISTS idx_price_date ON price_history(date);
        CREATE INDEX IF NOT EXISTS idx_event_dates ON events(start_date, end_date);
        CREATE INDEX IF NOT EXISTS idx_suggestions_date ON pricing_suggestions(date);
        """
        self.execute(schema)
        logger.info("Database schema initialized")
        
        # Inserisci competitor se non esistono
        for comp in COMPETITORS:
            self.execute(
                "INSERT INTO competitors (name, airbnb_id, url) VALUES (%s, %s, %s) ON CONFLICT (airbnb_id) DO NOTHING",
                (comp['name'], comp['airbnb_id'], comp['url'])
            )
        
        # Inserisci eventi 2026 se non esistono
        for event in EVENTS_2026:
            self.execute(
                """INSERT INTO events (name, start_date, end_date, category, impact_score, multiplier) 
                   VALUES (%s, %s, %s, %s, %s, %s) 
                   ON CONFLICT DO NOTHING""",
                (event['name'], event['start'], event['end'], event['category'], 
                 event['impact'], event['multiplier'])
            )
        logger.info("Initial data loaded")


class AirbnbScraper:
    """Scraper Airbnb con protezioni anti-ban"""
    
    def __init__(self):
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
        ]
    
    def smart_delay(self):
        """Delay randomizzato tra richieste"""
        delay = random.uniform(10, 18)  # 10-18 secondi
        logger.info(f"Waiting {delay:.1f}s before next request...")
        time.sleep(delay)
    
    def get_headers(self):
        """Headers realistici con user-agent random"""
        return {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }
    
    def scrape_listing(self, url: str, check_date: date) -> Optional[Dict]:
        """
        Scrape singolo listing Airbnb
        NOTA: Questo è un esempio base. Airbnb blocca scraping,
        quindi in produzione serve un servizio API o proxy.
        """
        try:
            # Aggiungi parametri date all'URL
            check_in = check_date.strftime('%Y-%m-%d')
            check_out = (check_date + timedelta(days=1)).strftime('%Y-%m-%d')
            
            params_url = f"{url}?adults=2&check_in={check_in}&check_out={check_out}"
            
            response = requests.get(params_url, headers=self.get_headers(), timeout=15)
            
            if response.status_code == 200:
                # Parsing HTML (esempio base)
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # NOTA: Il parsing effettivo dipende dalla struttura HTML di Airbnb
                # che cambia spesso. Questo è un placeholder.
                
                # In alternativa, cerca dati JSON nella pagina
                scripts = soup.find_all('script', type='application/json')
                for script in scripts:
                    try:
                        data = json.loads(script.string)
                        # Cerca prezzo nei dati JSON
                        # (la struttura varia, questo è un esempio)
                        if 'price' in str(data):
                            # Estrai prezzo (logica da adattare)
                            pass
                    except:
                        continue
                
                # Per ora, ritorna dati mock per testing
                return {
                    'available': True,
                    'price': random.randint(40, 80),  # Mock price
                    'scraped_at': datetime.now()
                }
            else:
                logger.warning(f"HTTP {response.status_code} for {url}")
                return None
                
        except Exception as e:
            logger.error(f"Scraping error for {url}: {e}")
            return None


class PricingEngine:
    """Motore calcolo prezzi dinamici"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def get_event_for_date(self, target_date: date) -> Optional[Dict]:
        """Trova evento attivo per una data"""
        results = self.db.execute(
            """SELECT name, category, impact_score, multiplier 
               FROM events 
               WHERE %s BETWEEN start_date AND end_date 
               ORDER BY impact_score DESC LIMIT 1""",
            (target_date,),
            fetch=True
        )
        return dict(results[0]) if results else None
    
    def get_season_multiplier(self, target_date: date) -> float:
        """Calcola moltiplicatore stagionale"""
        month = target_date.month
        
        if month in [6, 7, 8]:  # Estate
            return 1.2
        elif month in [4, 5, 9, 10]:  # Primavera/Autunno
            return 1.1
        elif month in [12, 1, 2]:  # Inverno (escluso Olimpiadi)
            return 0.95
        else:
            return 1.0
    
    def get_dow_multiplier(self, target_date: date) -> float:
        """Moltiplicatore giorno settimana"""
        dow = target_date.weekday()
        
        if dow in [4, 5]:  # Ven-Sab
            return PRICES_CONFIG['WEEKEND_MULTIPLIER']
        elif dow == 6:  # Domenica
            return PRICES_CONFIG['SUNDAY_DISCOUNT']
        else:
            return 1.0
    
    def get_market_average(self, target_date: date) -> Optional[float]:
        """Media prezzi competitor per una data"""
        results = self.db.execute(
            """SELECT AVG(price) as avg_price 
               FROM price_history 
               WHERE date = %s AND available = true AND price > 0""",
            (target_date,),
            fetch=True
        )
        
        if results and results[0]['avg_price']:
            return float(results[0]['avg_price'])
        return None
    
    def calculate_optimal_price(self, target_date: date) -> Dict:
        """
        Calcola prezzo ottimale con logica dinamica
        """
        # Base price
        dow = target_date.weekday()
        if dow in [4, 5]:  # Weekend
            base_price = PRICES_CONFIG['BASE_WEEKEND']
        else:
            base_price = PRICES_CONFIG['BASE_WEEKDAY']
        
        reasoning = {
            'base_price': base_price,
            'factors': []
        }
        
        # 1. Eventi
        event = self.get_event_for_date(target_date)
        if event:
            event_mult = float(event['multiplier'])
            reasoning['event'] = {
                'name': event['name'],
                'multiplier': event_mult
            }
            reasoning['factors'].append(f"Evento: {event['name']} (x{event_mult})")
        else:
            event_mult = 1.0
        
        # 2. Stagionalità
        season_mult = self.get_season_multiplier(target_date)
        reasoning['season_multiplier'] = season_mult
        if season_mult != 1.0:
            reasoning['factors'].append(f"Stagione (x{season_mult})")
        
        # 3. Giorno settimana
        dow_mult = self.get_dow_multiplier(target_date)
        reasoning['dow_multiplier'] = dow_mult
        if dow_mult != 1.0:
            day_name = ['Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab', 'Dom'][dow]
            reasoning['factors'].append(f"Giorno: {day_name} (x{dow_mult})")
        
        # 4. Media mercato (adjustment)
        market_avg = self.get_market_average(target_date)
        market_adj = 0
        if market_avg:
            market_adj = (market_avg - base_price) * 0.3  # 30% peso mercato
            reasoning['market_avg'] = market_avg
            reasoning['market_adjustment'] = round(market_adj, 2)
            reasoning['factors'].append(f"Mercato: €{market_avg:.0f} (adj: €{market_adj:+.0f})")
        
        # Calcolo finale
        calculated_price = (base_price + market_adj) * event_mult * season_mult * dow_mult
        
        # Limiti
        final_price = max(
            PRICES_CONFIG['MIN_PRICE'],
            min(PRICES_CONFIG['MAX_PRICE'], calculated_price)
        )
        
        reasoning['calculated'] = round(calculated_price, 2)
        reasoning['final'] = round(final_price, 0)
        
        # Confidence (quanto siamo sicuri)
        confidence = 0.7
        if market_avg:
            confidence += 0.2
        if event:
            confidence += 0.1
        
        return {
            'date': target_date,
            'suggested_price': round(final_price, 0),
            'base_price': base_price,
            'market_avg': market_avg,
            'event_multiplier': event_mult if event else None,
            'event_name': event['name'] if event else None,
            'reasoning': reasoning,
            'confidence': round(confidence, 2)
        }


class MilanoExpressBot:
    """Bot Telegram principale"""
    
    def __init__(self):
        self.db = Database(DATABASE_URL)
        self.scraper = AirbnbScraper()
        self.pricing = PricingEngine(self.db)
        self.bot = Bot(token=BOT_TOKEN)
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /start"""
        welcome = """
🏠 *Milano Express - Pricing Bot*

Bot per monitoraggio prezzi Airbnb e suggerimenti dinamici.

*Comandi disponibili:*
/oggi - Analisi mercato oggi
/domani - Previsione domani
/settimana - Trend prossimi 7 giorni
/eventi - Eventi impattanti prossimi
/competitor - Prezzi competitor
/suggerisci - Prezzo ottimale per date
/help - Aiuto

Sviluppato per Milano Express B&B 🇮🇹
        """
        await update.message.reply_text(welcome, parse_mode='Markdown')
    
    async def oggi(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Analisi prezzo oggi"""
        today = date.today()
        
        result = self.pricing.calculate_optimal_price(today)
        
        message = f"""
📅 *Analisi per oggi* ({today.strftime('%d/%m/%Y')})

💰 *Prezzo suggerito: €{result['suggested_price']:.0f}*

📊 Dettagli:
• Prezzo base: €{result['base_price']:.0f}
"""
        
        if result['market_avg']:
            message += f"• Media mercato: €{result['market_avg']:.0f}\n"
        
        if result['event_name']:
            message += f"• Evento: {result['event_name']}\n"
        
        if result['reasoning']['factors']:
            message += "\n🔍 Fattori applicati:\n"
            for factor in result['reasoning']['factors']:
                message += f"  • {factor}\n"
        
        message += f"\n✅ Confidenza: {result['confidence']*100:.0f}%"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def domani(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Previsione domani"""
        tomorrow = date.today() + timedelta(days=1)
        
        result = self.pricing.calculate_optimal_price(tomorrow)
        
        message = f"""
📅 *Previsione per domani* ({tomorrow.strftime('%d/%m/%Y')})

💰 *Prezzo suggerito: €{result['suggested_price']:.0f}*

📊 Dettagli:
• Prezzo base: €{result['base_price']:.0f}
"""
        
        if result['event_name']:
            message += f"• ⭐ Evento: *{result['event_name']}*\n"
        
        message += f"\n✅ Confidenza: {result['confidence']*100:.0f}%"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def settimana(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Trend prossimi 7 giorni"""
        message = "📊 *Trend prossimi 7 giorni*\n\n"
        
        total = 0
        for i in range(7):
            target_date = date.today() + timedelta(days=i)
            result = self.pricing.calculate_optimal_price(target_date)
            
            day_name = ['Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab', 'Dom'][target_date.weekday()]
            event_emoji = "⭐" if result['event_name'] else ""
            
            message += f"{day_name} {target_date.strftime('%d/%m')}: *€{result['suggested_price']:.0f}* {event_emoji}\n"
            total += result['suggested_price']
        
        avg = total / 7
        message += f"\n💰 Media settimanale: €{avg:.0f}/notte"
        message += f"\n📈 Ricavo stimato: €{total:.0f}"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def eventi(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Eventi prossimi"""
        today = date.today()
        
        results = self.db.execute(
            """SELECT name, start_date, end_date, category, impact_score, multiplier 
               FROM events 
               WHERE end_date >= %s 
               ORDER BY start_date LIMIT 10""",
            (today,),
            fetch=True
        )
        
        if not results:
            await update.message.reply_text("Nessun evento trovato nei prossimi mesi.")
            return
        
        message = "📅 *Eventi prossimi con impatto prezzi:*\n\n"
        
        for event in results:
            start = event['start_date']
            end = event['end_date']
            days_until = (start - today).days
            
            if days_until < 0:
                status = "🟢 In corso"
            elif days_until <= 7:
                status = f"🔴 Tra {days_until} giorni"
            elif days_until <= 30:
                status = f"🟡 Tra {days_until} giorni"
            else:
                status = f"⚪ Tra {days_until} giorni"
            
            message += f"{status}\n"
            message += f"*{event['name']}*\n"
            message += f"📍 {start.strftime('%d/%m')} - {end.strftime('%d/%m/%Y')}\n"
            message += f"💰 Moltiplicatore: x{event['multiplier']}\n\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /help"""
        help_text = """
🤖 *Comandi disponibili:*

📊 *Analisi Prezzi*
/oggi - Prezzo suggerito oggi
/domani - Previsione domani
/settimana - Trend 7 giorni
/competitor - Prezzi competitor

📅 *Eventi*
/eventi - Lista eventi importanti
/olimpiadi - Info Olimpiadi 2026
/salone - Info Salone Mobile 2026

⚙️ *Altro*
/help - Questo messaggio

💡 *Suggerimento:* Il bot invia automaticamente aggiornamenti quotidiani alle 7:00 e report settimanali il lunedì.
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def send_daily_report(self):
        """Report giornaliero automatico"""
        today = date.today()
        result = self.pricing.calculate_optimal_price(today)
        
        message = f"""
☀️ *Report Giornaliero* - {today.strftime('%d/%m/%Y')}

💰 *Prezzo suggerito oggi: €{result['suggested_price']:.0f}*
"""
        
        if result['event_name']:
            message += f"\n⭐ *Evento oggi:* {result['event_name']}"
        
        # Prossimi eventi (48h)
        tomorrow = today + timedelta(days=1)
        result_tomorrow = self.pricing.calculate_optimal_price(tomorrow)
        
        if result_tomorrow['event_name']:
            message += f"\n\n🔔 *Domani:* {result_tomorrow['event_name']}"
            message += f"\nPrezzo suggerito: €{result_tomorrow['suggested_price']:.0f}"
        
        message += "\n\n📊 Usa /settimana per vedere il trend settimanale"
        
        await self.bot.send_message(chat_id=GROUP_CHAT_ID, text=message, parse_mode='Markdown')
        logger.info("Daily report sent")


def main():
    """Main bot application"""
    # Inizializza database
    db = Database(DATABASE_URL)
    db.init_schema()
    
    # Crea bot
    bot_instance = MilanoExpressBot()
    
    # Setup Telegram application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Registra comandi
    application.add_handler(CommandHandler("start", bot_instance.start))
    application.add_handler(CommandHandler("oggi", bot_instance.oggi))
    application.add_handler(CommandHandler("domani", bot_instance.domani))
    application.add_handler(CommandHandler("settimana", bot_instance.settimana))
    application.add_handler(CommandHandler("eventi", bot_instance.eventi))
    application.add_handler(CommandHandler("help", bot_instance.help_command))
    
    # TODO: Job queue per report automatici
    # job_queue = application.job_queue
    # job_queue.run_daily(bot_instance.send_daily_report, time=datetime.time(7, 0))
    
    logger.info("Bot started successfully!")
    
    # Run bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
