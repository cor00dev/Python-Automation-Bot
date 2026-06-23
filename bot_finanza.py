import logging, random, sqlite3, asyncio, yfinance as yf, os
from dotenv import load_dotenv
from datetime import datetime
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, BufferedInputFile

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

load_dotenv()

ADMIN_ID = int(os.getenv("ADMIN_ID"))
TOKEN = os.getenv("BOT_TOKEN")

router = Router()

class FinanzaFSM(StatesGroup):
    attesa_budget = State()
    attesa_rischio = State()

def inizializza_db():
    conn = sqlite3.connect('finanza_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS utenti (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            budget INTEGER,
            rischio TEXT
        )            
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticket (
            user_id INTEGER PRIMARY KEY,
            ultima_segnalazione TEXT
        )
    ''')
    conn.commit()
    conn.close()
    
inizializza_db()

@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    user_name = message.from_user.first_name
    ora = datetime.now().hour
    
    if 5 <= ora < 12:
        saluto = f"Buongiorno {user_name}!"
    elif 12 <= ora < 18:
        saluto = f"Buon pomeriggio {user_name}!"
    else:
        saluto = f"Buonasera {user_name}!"
        
    await message.answer(f"{saluto} Sono il tuo bot per finanza! Digita il tuo budget:")
    
    await state.set_state(FinanzaFSM.attesa_budget)

@router.message(FinanzaFSM.attesa_budget, F.text)
async def ricevi_budget(message: Message, state: FSMContext):
    budget = message.text
    user_id = message.from_user.id
    username = message.from_user.username
    
    try:
        budget_int = int(budget)
        
        conn = sqlite3.connect('finanza_bot.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO utenti (user_id, username, budget, rischio)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET budget = excluded.budget, username = excluded.username ''',
            (user_id, username, budget_int, None))
        conn.commit()
        conn.close()
        
        tastiera_pronta = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Basso 🟢", callback_data="basso"),
                InlineKeyboardButton(text="Medio 🟡", callback_data="medio"),
                InlineKeyboardButton(text="Alto 🔴", callback_data="alto")
            ]
        ])
        
        await message.answer("Scegli la tua propensione al rischio:", reply_markup=tastiera_pronta)
        
        await state.set_state(FinanzaFSM.attesa_rischio)
        
    except ValueError:
        await message.answer("⚠️ Errore: Inserisci un numero valido per il budget.")
    except Exception as p:
        await message.answer(f"Operazione annullata: ERRORE {p}")

@router.callback_query(FinanzaFSM.attesa_rischio)
async def invia_report(callback: CallbackQuery, state: FSMContext):
    await callback.answer() 
    
    user_id = callback.from_user.id
    rischio_scelto = callback.data
    nome_utente = callback.from_user.first_name
    
    conn = sqlite3.connect('finanza_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT budget FROM utenti WHERE user_id = ?', (user_id,))
    riga = cursor.fetchone()
    
    if riga is None:
        conn.close() 
        await callback.message.answer("⚠️ Sessione non trovata. Digita /start per ricominciare.")
        await state.clear()
        return
    
    budget_scelto = riga[0]
    
    cursor.execute('UPDATE utenti SET rischio = ? WHERE user_id = ?', (rischio_scelto, user_id))
    conn.commit()
    conn.close()
    
    await callback.message.edit_text(text=f"Hai scelto il rischio {rischio_scelto}")
    
    if rischio_scelto == 'basso':
        obbligazioni = int(budget_scelto * 0.8)
        liquidita = int(budget_scelto * 0.02)
        consiglio = (
            f"Consulenza personalizzata per {nome_utente}:\n\n"
            f"🟢 **Profilo Conservativo**\n"
            f"Il tuo obiettivo principale è proteggere il capitale.\n\n"
            f"Ecco una simulazione di allocazione del tuo budget ({budget_scelto}€):\n"
            f"• 🏦 Sicurezza: **{liquidita}€**\n"
            f"• 📜 Difesa: **{obbligazioni}€**\n"
            f"• 📈 Crescita: **0€**"
        )
    elif rischio_scelto == 'medio':
        azioni = int(budget_scelto * 0.5)
        obbligazioni = int(budget_scelto * 0.4)
        liquidita = int(budget_scelto * 0.1)
        consiglio = (
            f"Consulenza personalizzata per {nome_utente}:\n\n"
            f"🟡 **Profilo Bilanciato**\n"
            f"Ecco una simulazione di allocazione del tuo budget ({budget_scelto}€):\n"
            f"• 🏦 Sicurezza: **{liquidita}€**\n"
            f"• 📜 Difesa: **{obbligazioni}€**\n"
            f"• 📈 Crescita: **{azioni}€**"
        )
    elif rischio_scelto == 'alto':
        azioni = int(budget_scelto * 0.85)
        obbligazioni = int(budget_scelto * 0.15)
        consiglio = (
            f"Consulenza personalizzata per {nome_utente}:\n\n"
            f"🔴 **Profilo Aggressivo**\n"
            f"Ecco una simulazione di allocazione del tuo budget ({budget_scelto}€):\n"
            f"• 📈 Crescita: **{azioni}€**\n"
            f"• 📜 Difesa: **{obbligazioni}€**\n"
            f"• 🚀 Speculazione: **Un piccolo extra facoltativo**"
        )
        
    await callback.message.answer(consiglio, parse_mode="Markdown")
   
    await state.clear()

@router.message(Command("stop", "annulla"))
async def stop(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Operazione annullata dall'utente.")

@router.message(Command("segnala"))
async def segnala(message: Message):
    user_id = message.from_user.id
    ora_attuale = datetime.now()
    
    conn = sqlite3.connect('finanza_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT ultima_segnalazione FROM ticket WHERE user_id = ?', (user_id,))
    riga = cursor.fetchone()
    
    if riga:
        ultima_segnalazione = datetime.strptime(riga[0], "%Y-%m-%d %H:%M:%S.%f")
        secondi_passati = (ora_attuale - ultima_segnalazione).total_seconds()
        
        if secondi_passati < 60:
            secondi_rimanenti = int(60 - secondi_passati)
            conn.close()
            await message.answer(f"Ti mancano ancora {secondi_rimanenti} secondi.")
            return
            
    ticket = random.randint(1000, 9999)
    ora_stringa = str(ora_attuale) # In sqlite va convertita in stringa
    
    cursor.execute('''
        INSERT INTO ticket (user_id, ultima_segnalazione)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET ultima_segnalazione = excluded.ultima_segnalazione ''',
        (user_id, ora_stringa))
    conn.commit()
    conn.close()
    
    nome_utente = message.from_user.first_name
    username_formattato = message.from_user.username or "Nessuno"
    data_formattata = ora_attuale.strftime("%d/%m/%Y %H:%M:%S")
    
    contenuto_file = (
        f"===================================\n"
        f"       RICEVUTA TICKET #{ticket}\n"
        f"===================================\n\n"
        f"Data Inserimento: {data_formattata}\n"
        f"Utente: {nome_utente} (@{username_formattato})\n"
    )
    
    invio_file = BufferedInputFile(contenuto_file.encode('utf-8'), filename=f"ticket_{ticket}.txt")
    
    await message.answer(f"✅ Segnalazione avvenuta con successo, numero ticket: {ticket}")
    await message.bot.send_document(
        chat_id=message.chat.id,
        document=invio_file,
        caption=f"📋 Ecco il promemoria ufficiale per il tuo Ticket #{ticket}"
    )

@router.message(Command("help"))
async def help_cmd(message: Message):
    testo = (
        f"Ciao {message.from_user.first_name}!\nI comandi disponibili sono:\n\n"
        "🟢 /start = Inizia la tua consulenza personalizzata\n"
        "📈 /prezzo = Controlla le quotazioni in tempo reale (es. /prezzo BTC-USD)\n"
        "🚨 /segnala = Per segnalare bug o malfunzionamenti\n"
        "❌ /stop = Per annullare ogni operazione in esecuzione\n"
    )
    if message.chat.id == ADMIN_ID:
        testo += "\n⛔ADMIN⛔\n📊 /stats = Statistiche\n📢 /broadcast [msg] = Invia a tutti"
        
    await message.answer(testo)

@router.message(Command("stats"))
async def stats(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Non hai i permessi di usare questo comando")
        return
        
    conn = sqlite3.connect('finanza_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*), SUM(budget) FROM utenti')
    res_utenti = cursor.fetchone()
    
    cursor.execute('SELECT COUNT(*) FROM ticket')
    res_ticket = cursor.fetchone()
    conn.close()
    
    utenti_totali = res_utenti[0] or 0
    budget_totali = res_utenti[1] or 0
    ticket_totali = res_ticket[0] or 0
    
    testo_stats = (
        f"📊 **PANNELLO AMMINISTRATORE** 📊\n\n"
        f"• 👥 Utenti totali: **{utenti_totali}**\n"
        f"• 💰 Budget totale: **{budget_totali}€**\n"
        f"• 📋 Ticket aperti: **{ticket_totali}**"
    )
    await message.answer(testo_stats, parse_mode='Markdown')

@router.message(Command("broadcast"))
async def broadcast(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Non hai i permessi di usare questo comando")
        return
        
    parti_testo = message.text.split(' ', 1)
    if len(parti_testo) < 2:
        await message.answer("⚠️ **Uso corretto:** `/broadcast Il tuo messaggio qui`", parse_mode="Markdown")
        return
        
    messaggio_da_inviare = parti_testo[1]
    
    conn = sqlite3.connect('finanza_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM utenti')
    utenti = cursor.fetchall()
    conn.close()
    
    if not utenti:
        await message.answer('❌ Non ci sono utenti registrati.')
        return
        
    await message.answer(f'Invio dei messaggi a {len(utenti)} utenti in corso...')
    
    inviati = falliti = 0
    for utente in utenti:
        try:
            await message.bot.send_message(chat_id=utente[0], text=messaggio_da_inviare)
            inviati += 1
        except Exception:
            falliti += 1
            
    await message.answer(f"📢 **Broadcast Completato!**\n✅ Consegnati: {inviati}\n❌ Falliti: {falliti}")

@router.message(Command('prezzo'))
async def check_price(message: Message):
    args = message.text.split(' ', 1)
    
    if len(args) < 2:
        await message.answer(
            "⚠️ **Uso corretto:** `/prezzo <simbolo> or <azienda>`\n"
            "Esempi:\n"
            "• Azioni: `/prezzo AAPL or (Apple)` o `/prezzo TSLA or (Tesla)`\n"
            "• Crypto: `/prezzo BTC-USD or (Bitcoin)`", 
            parse_mode="Markdown"
        )
        return
    
    query_ricerca = args[1]
    messaggio_attesa = await message.answer(f"⏳ Recupero i dati in tempo reale per **{query_ricerca}**...", parse_mode="Markdown")
    
    def esegui_ricerca():
        try:
            ricerca = yf.Search(query_ricerca, max_results=5)
            return ricerca.quotes
        except Exception:
            return []
        
    risultati = await asyncio.to_thread(esegui_ricerca)
    
    if not risultati:
        await messaggio_attesa.edit_text("❌ Nessun asset trovato con questo nome. Riprova con parole diverse.")
        return
    
    primo_risultato = risultati[0]
    symbol = primo_risultato.get('symbol')
    shortname = primo_risultato.get('shortname') or primo_risultato.get('longname') or "Nome non disponibile"
    
    def fetch_data():
        ticker = yf.Ticker(symbol)
        return ticker.history(period='1d')
    
    try:
        data = await asyncio.to_thread(fetch_data)
        
        if data.empty:
            await messaggio_attesa.edit_text(f"❌ Nessun dato trovato per il simbolo **{symbol}**. Controlla che sia corretto.", parse_mode="Markdown")
            
        prezzo_attuale = data['Close'].iloc[-1]
        
        testo_risposta = (
            f"📈 **Dati di Mercato: {shortname} {symbol}**\n\n"
            f"💵 Prezzo attuale: **${prezzo_attuale:.2f} USD**\n"
            f"🕒 Aggiornato al: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        )
        await messaggio_attesa.edit_text(testo_risposta, parse_mode='Markdown')
    except Exception as p:
        await messaggio_attesa.edit_text(f"⚠️ Errore tecnico durante il recupero dei dati dell'API: {p}")
    
async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    
    print("Bot pronto...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())