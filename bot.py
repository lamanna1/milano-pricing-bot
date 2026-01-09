#!/usr/bin/env python3
"""
Milano Express - Pricing Bot v2.1 FINAL
Calibrato su dati reali mercato Seveso/Milano Nord
"""

import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/healthz", "/"):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.end_headers()

def start_health_server():
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()

threading.Thread(target=start_health_server, daemon=True).start()
import logging
import random
import threading
from datetime import datetime, timedelta, date
from typing import Optional, Dict, List

import psycopg2
from psycopg2.extras import RealDictCursor
import requests
import feedparser
from bs4 import BeautifulSoup
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from http.server import HTTPServer, BaseHTTPRequestHandler

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Environment variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
GROUP_CHAT_ID_RAW = os.environ.get("GROUP_CHAT_ID")
GROUP_CHAT_ID = int(GROUP_CHAT_ID_RAW) if GROUP_CHAT_ID_RAW else None
EVENTBRITE_TOKEN = os.environ.get("EVENTBRITE_TOKEN", "")

if not BOT_TOKEN:
    raise RuntimeError("Missing BOT_TOKEN")
if not DATABASE_URL:
    raise RuntimeError("Missing DATABASE_URL")

# PREZZI OTTIMIZZATI - Basati su analisi mercato reale
PRICES_CONFIG = {
    "BASE_WEEKDAY": 80,      # Settimana (competitor €109-122, noi sotto)
    "BASE_WEEKEND": 105,     # Weekend (competitor €113-122, noi competitivi)
    "MIN_PRICE": 70,         # Mai svendere
    "MAX_PRICE": 250,        # Sfruttiamo eventi al massimo
    "WEEKEND_MULTIPLIER": 1.15,
    "SUNDAY_DISCOUNT": 0.95,
}

# EVENTI FISSI 2026 - Moltiplicatori calibrati su mercato reale
FIXED_EVENTS_2026 = [
    {
        "name": "Olimpiadi Invernali Milano-Cortina",
        "start": "2026-02-06",
        "end": "2026-02-22",
        "impact": 10,
        "multiplier": 2.5,  # Competitor €160-195, noi €200-260
        "category": "olimpiadi",
    },
    {
        "name": "Paralimpiadi Invernali",
        "start": "2026-03-06",
        "end": "2026-03-15",
        "impact": 8,
        "multiplier": 1.8,
        "category": "paralimpiadi",
    },
    {
        "name": "Salone del Mobile Milano",
        "start": "2026-04-21",
        "end": "2026-04-26",
        "impact": 10,
        "multiplier": 2.0,  # OPPORTUNITÀ! Competitor €107, noi €160-200
        "category": "fiera",
    },
    {
        "name": "Milano Fashion Week Uomo FW",
        "start": "2026-01-16",
        "end": "2026-01-20",
        "impact": 6,
        "multiplier": 1.3,  # Competitor €122, noi €104-136
        "category": "moda",
    },
    {
        "name": "Milano Fashion Week Uomo SS",
        "start": "2026-06-19",
        "end": "2026-06-23",
        "impact": 6,
        "multiplier": 1.3,
        "category": "moda",
    },
    {
        "name": "HOMI Milano",
        "start": "2026-01-22",
        "end": "2026-01-25",
        "impact": 5,
        "multiplier": 1.2,
        "category": "fiera",
    },
    {
        "name": "MICAM Milano",
        "start": "2026-02-22",
        "end": "2026-02-24",
        "impact": 5,
        "multiplier": 1.25,
        "category": "fiera",
    },
    {
        "name": "LINEAPELLE",
        "start": "2026-02-11",
        "end": "2026-02-13",
        "impact": 4,
        "multiplier": 1.15,
        "category": "fiera",
    },
    {
        "name": "TUTTOFOOD",
        "start": "2026-05-11",
        "end": "2026-05-14",
        "impact": 6,
        "multiplier": 1.35,
        "category": "fiera",
    },
    {
        "name": "GP Italia Formula 1 Monza",
        "start": "2026-09-04",
        "end": "2026-09-06",
        "impact": 9,
        "multiplier": 1.8,  # Competitor €172-254, noi €145-190
        "category": "sport",
    },
]

# Competitor (per futura integrazione)
COMPETITORS = [
    {
        "name": "Competitor 1",
        "airbnb_id": "1160107109343011290",
        "url": "https://www.airbnb.it/rooms/1160107109343011290",
    },
    {
        "name": "Competitor 2",
        "airbnb_id": "845070499530356430",
        "url": "https://www.airbnb.it/rooms/845070499530356430",
    },
    {
        "name": "Competitor 3",
        "airbnb_id": "1315093379066044987",
        "url": "https://www.airbnb.it/rooms/1315093379066044987",
    },
    {
        "name": "Competitor 4",
        "airbnb_id": "890625863311377711",
        "url": "https://www.airbnb.it/rooms/890625863311377711",
    },
    {
        "name": "Competitor 5",
        "airbnb_id": "1180138186052044350",
        "url": "https://www.airbnb.it/rooms/1180138186052044350",
    },
]


class Database:
    def __init__(self, url: str):
        self.url = url
        self.conn = None

    def connect(self):
        if not self.conn or self.conn.closed:
            self.conn = psycopg2.connect(self.url)
        return self.conn

    def execute(self, query: str, params: tuple = None, fetch: bool = False):
        conn = self.connect()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            if fetch:
                return cur.fetchall()
            conn.commit()
        return None

    def init_schema(self):
        # Drop old schema if exists (per fix colonna source)
        drop_schema = """
        DROP TABLE IF EXISTS price_adjustments CASCADE;
        DROP TABLE IF EXISTS pricing_suggestions CASCADE;
        DROP TABLE IF EXISTS price_history CASCADE;
        DROP TABLE IF EXISTS events CASCADE;
        DROP TABLE IF EXISTS competitors CASCADE;
        """
        
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
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(name, start_date, end_date)
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

        CREATE INDEX IF NOT EXISTS idx_price_date ON price_history(date);
        CREATE INDEX IF NOT EXISTS idx_event_dates ON events(start_date, end_date);
        CREATE INDEX IF NOT EXISTS idx_suggestions_date ON pricing_suggestions(date);
        """
        
        try:
            self.execute(drop_schema)
            logger.info("Dropped old schema")
        except Exception as e:
            logger.warning(f"Error dropping old schema (ok if first run): {e}")
        
        self.execute(schema)
        logger.info("Database schema initialized")

        # Inserisci competitor
        for comp in COMPETITORS:
            self.execute(
                "INSERT INTO competitors (name, airbnb_id, url) VALUES (%s, %s, %s) "
                "ON CONFLICT (airbnb_id) DO NOTHING",
                (comp["name"], comp["airbnb_id"], comp["url"]),
            )

        # Inserisci eventi fissi (SENZA colonna source)
        for event in FIXED_EVENTS_2026:
            self.execute(
                "INSERT INTO events (name, start_date, end_date, category, impact_score, multiplier) "
                "VALUES (%s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (name, start_date, end_date) DO NOTHING",
                (
                    event["name"],
                    event["start"],
                    event["end"],
                    event["category"],
                    event["impact"],
                    event["multiplier"],
                ),
            )

        logger.info("Initial data loaded")


class EventFetcher:
    """Fetch eventi da fonti esterne (opzionale)"""

    def __init__(self, db: Database):
        self.db = db

    def fetch_fieramilano_rss(self) -> List[Dict]:
        """Legge RSS Fiera Milano"""
        try:
            feed_url = "https://www.fieramilano.it/feed"
            feed = feedparser.parse(feed_url)

            events = []
            for entry in feed.entries[:10]:
                event = {
                    "name": entry.title,
                    "description": entry.get("summary", ""),
                    "link": entry.link,
                    "category": "fiera",
                }
                events.append(event)
                logger.info(f"RSS Fiera Milano: {entry.title}")

            return events
        except Exception as e:
            logger.error(f"Error fetching Fiera Milano RSS: {e}")
            return []

    def update_events_from_sources(self):
        """Aggiorna eventi da RSS (opzionale)"""
        logger.info("Checking for new events from RSS...")
        rss_events = self.fetch_fieramilano_rss()
        logger.info(f"Found {len(rss_events)} events from RSS")


class PricingEngine:
    def __init__(self, db: Database):
        self.db = db

    def get_event_for_date(self, target_date: date) -> Optional[Dict]:
        results = self.db.execute(
            "SELECT name, category, impact_score, multiplier "
            "FROM events "
            "WHERE %s BETWEEN start_date AND end_date "
            "ORDER BY impact_score DESC LIMIT 1",
            (target_date,),
            fetch=True,
        )
        return dict(results[0]) if results else None

    def get_season_multiplier(self, target_date: date) -> float:
        """Stagionalità calibrata su mercato reale"""
        month = target_date.month
        # Estate: competitor NON alzano molto (€113 vs €122 inverno!)
        if month in [6, 7, 8]:
            return 1.05  # Era 1.2, ora realistico
        if month in [4, 5, 9, 10]:
            return 1.1
        if month in [12, 1, 2]:
            return 1.0
        return 1.0

    def get_dow_multiplier(self, target_date: date) -> float:
        dow = target_date.weekday()
        if dow in [4, 5]:
            return PRICES_CONFIG["WEEKEND_MULTIPLIER"]
        if dow == 6:
            return PRICES_CONFIG["SUNDAY_DISCOUNT"]
        return 1.0

    def get_market_average(self, target_date: date) -> Optional[float]:
        results = self.db.execute(
            "SELECT AVG(price) as avg_price "
            "FROM price_history "
            "WHERE date = %s AND available = true AND price > 0",
            (target_date,),
            fetch=True,
        )
        if results and results[0]["avg_price"]:
            return float(results[0]["avg_price"])
        return None

    def calculate_optimal_price(self, target_date: date) -> Dict:
        dow = target_date.weekday()
        base_price = PRICES_CONFIG["BASE_WEEKEND"] if dow in [4, 5] else PRICES_CONFIG["BASE_WEEKDAY"]

        reasoning = {"base_price": base_price, "factors": []}

        # Eventi
        event = self.get_event_for_date(target_date)
        event_mult = 1.0
        if event:
            event_mult = float(event["multiplier"])
            reasoning["event"] = {"name": event["name"], "multiplier": event_mult}
            reasoning["factors"].append(f"Evento: {event['name']} (x{event_mult})")

        # Stagionalità
        season_mult = self.get_season_multiplier(target_date)
        reasoning["season_multiplier"] = season_mult
        if season_mult != 1.0:
            reasoning["factors"].append(f"Stagione (x{season_mult})")

        # Giorno settimana
        dow_mult = self.get_dow_multiplier(target_date)
        reasoning["dow_multiplier"] = dow_mult
        if dow_mult != 1.0:
            day_name = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"][dow]
            reasoning["factors"].append(f"Giorno: {day_name} (x{dow_mult})")

        # Mercato (opzionale se disponibile)
        market_avg = self.get_market_average(target_date)
        market_adj = 0.0
        if market_avg:
            market_adj = (market_avg - base_price) * 0.3
            reasoning["market_avg"] = market_avg
            reasoning["market_adjustment"] = round(market_adj, 2)
            reasoning["factors"].append(f"Mercato: €{market_avg:.0f} (adj: €{market_adj:+.0f})")

        calculated_price = (base_price + market_adj) * event_mult * season_mult * dow_mult
        final_price = max(PRICES_CONFIG["MIN_PRICE"], min(PRICES_CONFIG["MAX_PRICE"], calculated_price))

        reasoning["calculated"] = round(calculated_price, 2)
        reasoning["final"] = round(final_price, 0)

        confidence = 0.75  # Base confidence
        if market_avg:
            confidence += 0.15
        if event:
            confidence += 0.1

        return {
            "date": target_date,
            "suggested_price": round(final_price, 0),
            "base_price": base_price,
            "market_avg": market_avg,
            "event_multiplier": event_mult if event else None,
            "event_name": event["name"] if event else None,
            "reasoning": reasoning,
            "confidence": min(round(confidence, 2), 1.0),
        }


class MilanoExpressBot:
    def __init__(self):
        self.db = Database(DATABASE_URL)
        self.pricing = PricingEngine(self.db)
        self.event_fetcher = EventFetcher(self.db)
        self.bot = Bot(token=BOT_TOKEN)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        welcome = (
            "🏠 *Milano Express - Pricing Bot*\n\n"
            "Bot per suggerimenti prezzi dinamici basati su eventi e mercato.\n\n"
            "*Comandi disponibili:*\n"
            "/oggi - Prezzo suggerito oggi\n"
            "/domani - Previsione domani\n"
            "/settimana - Trend 7 giorni\n"
            "/eventi - Eventi prossimi 2026\n"
            "/help - Lista comandi\n\n"
            "📍 Calibrato su mercato reale Seveso/Milano Nord\n"
            "Sviluppato per Milano Express B&B 🇮🇹"
        )
        await update.message.reply_text(welcome, parse_mode="Markdown")

    async def oggi(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        today = date.today()
        result = self.pricing.calculate_optimal_price(today)

        message = (
            f"📅 *Analisi per oggi* ({today.strftime('%d/%m/%Y')})\n\n"
            f"💰 *Prezzo suggerito: €{result['suggested_price']:.0f}*\n\n"
            "📊 Dettagli:\n"
            f"• Prezzo base: €{result['base_price']:.0f}\n"
        )

        if result["market_avg"]:
            message += f"• Media mercato: €{result['market_avg']:.0f}\n"
        if result["event_name"]:
            message += f"• 🎯 Evento: {result['event_name']}\n"
        if result["reasoning"]["factors"]:
            message += "\n🔍 Fattori applicati:\n"
            for factor in result["reasoning"]["factors"]:
                message += f"  • {factor}\n"

        message += f"\n✅ Confidenza: {result['confidence'] * 100:.0f}%"
        await update.message.reply_text(message, parse_mode="Markdown")

    async def domani(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        tomorrow = date.today() + timedelta(days=1)
        result = self.pricing.calculate_optimal_price(tomorrow)

        message = (
            f"📅 *Previsione per domani* ({tomorrow.strftime('%d/%m/%Y')})\n\n"
            f"💰 *Prezzo suggerito: €{result['suggested_price']:.0f}*\n\n"
            "📊 Dettagli:\n"
            f"• Prezzo base: €{result['base_price']:.0f}\n"
        )

        if result["event_name"]:
            message += f"• ⭐ Evento: *{result['event_name']}*\n"

        message += f"\n✅ Confidenza: {result['confidence'] * 100:.0f}%"
        await update.message.reply_text(message, parse_mode="Markdown")

    async def settimana(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message = "📊 *Trend prossimi 7 giorni*\n\n"
        total = 0.0

        for i in range(7):
            target_date = date.today() + timedelta(days=i)
            result = self.pricing.calculate_optimal_price(target_date)

            day_name = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"][target_date.weekday()]
            event_emoji = "🎯" if result["event_name"] else ""

            message += f"{day_name} {target_date.strftime('%d/%m')}: *€{result['suggested_price']:.0f}* {event_emoji}\n"
            total += float(result["suggested_price"])

        avg = total / 7.0
        message += f"\n💰 Media settimanale: €{avg:.0f}/notte"
        message += f"\n📈 Ricavo stimato 7gg: €{total:.0f}"
        await update.message.reply_text(message, parse_mode="Markdown")

    async def eventi(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        today = date.today()
        results = self.db.execute(
            "SELECT name, start_date, end_date, category, impact_score, multiplier "
            "FROM events "
            "WHERE end_date >= %s "
            "ORDER BY start_date LIMIT 15",
            (today,),
            fetch=True,
        )

        if not results:
            await update.message.reply_text("Nessun evento trovato nei prossimi mesi.")
            return

        message = "📅 *Eventi prossimi con impatto prezzi:*\n\n"

        for event in results:
            start = event["start_date"]
            end = event["end_date"]
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
            message += f"💰 Prezzo x{event['multiplier']}\n\n"

        await update.message.reply_text(message, parse_mode="Markdown")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = (
            "🤖 *Comandi disponibili:*\n\n"
            "📊 *Analisi Prezzi*\n"
            "/oggi - Prezzo suggerito oggi\n"
            "/domani - Previsione domani\n"
            "/settimana - Trend 7 giorni\n\n"
            "📅 *Eventi*\n"
            "/eventi - Lista eventi 2026\n\n"
            "⚙️ *Altro*\n"
            "/help - Questo messaggio\n\n"
            "💡 *Come funziona:*\n"
            "Il bot analizza eventi (Olimpiadi, Salone, Formula 1), "
            "stagionalità e giorno settimana per suggerire il prezzo ottimale.\n\n"
            "📈 *Prezzi base:* €80 settimana, €105 weekend\n"
            "🎯 *Range:* €70-250\n\n"
            "✨ *Calibrato su mercato reale Seveso/Milano Nord*"
        )
        await update.message.reply_text(help_text, parse_mode="Markdown")


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is running - Milano Express Pricing v2.1")

    def log_message(self, format, *args):
        return


def start_health_server():
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()


def main():
    # Init database
    db = Database(DATABASE_URL)
    db.init_schema()

    # Start health check server
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()
    logger.info(f"Health check server started on port {os.environ.get('PORT', '10000')}")

    # Init bot
    bot_instance = MilanoExpressBot()

    # Setup Telegram application
    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", bot_instance.start))
    application.add_handler(CommandHandler("oggi", bot_instance.oggi))
    application.add_handler(CommandHandler("domani", bot_instance.domani))
    application.add_handler(CommandHandler("settimana", bot_instance.settimana))
    application.add_handler(CommandHandler("eventi", bot_instance.eventi))
    application.add_handler(CommandHandler("help", bot_instance.help_command))

    logger.info("Bot started successfully! Milano Express Pricing v2.1")

    # Run bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
