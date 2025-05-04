import sqlite3
import random
from datetime import datetime
from telegram.ext import Updater, CommandHandler, CallbackContext
from telegram import Update
import os

# === Конфигурация ===
MINING_COST = 3000  # Цена фермы
MINING_INCOME = 35  # Доход в день
MAX_MINING_RIGS = 5  # Максимум ферм
BITCOIN_PRICE = 30000  # Цена BTC
SHARE_PRICES = {
    "Tesla": 250,
    "AMD": 150,
    "NVIDIA": 300,
    "Bitcoin Mining Inc": 500,
    "BlockDAG Network": 100,
    "Solana Foundation": 400
}

# === Квесты ===
QUESTS = [
    {
        "name": "Начальный капитал",
        "description": "Получите стартовый баланс $5000",
        "condition": lambda p: p["balance"] >= 5000,
        "reward": 1000
    },
    {
        "name": "Первые фермы",
        "description": "Купите 2 майнинг-фермы",
        "condition": lambda p: p["mining_rigs"] >= 2,
        "reward": 500
    },
    {
        "name": "Инвестор Tesla",
        "description": "Купите 5 акций Tesla",
        "condition": lambda p: p["shares"].get("Tesla", 0) >= 5,
        "reward": 300
    },
    {
        "name": "Приглашение друзей",
        "description": "Пригласите 3 друзей",
        "condition": lambda p: get_referral_count(p["user_id"]) >= 3,
        "reward": 1500
    },
    {
        "name": "Блокчейн-магнат",
        "description": "Купите 3 акции BlockDAG Network",
        "condition": lambda p: p["shares"].get("BlockDAG Network", 0) >= 3,
        "reward": 800
    },
    {
        "name": "Расширение бизнеса",
        "description": "Купите 5 майнинг-ферм",
        "condition": lambda p: p["mining_rigs"] >= 5,
        "reward": 2000
    }
]

# === Инициализация базы данных ===
def init_db():
    conn = sqlite3.connect('crypto_tycoon.db')
    c = conn.cursor()
    
    # Таблица игроков
    c.execute('''CREATE TABLE IF NOT EXISTS players
                 (user_id INTEGER PRIMARY KEY, 
                  balance REAL, 
                  mining_rigs INTEGER,
                  bitcoin_balance REAL,
                  day INTEGER,
                  quest_progress INTEGER,
                  ref_code TEXT)''')
    
    # Таблица акций
    for company in SHARE_PRICES:
        c.execute(f'''CREATE TABLE IF NOT EXISTS {company.lower().replace(" ", "_")}
                   (user_id INTEGER PRIMARY KEY, amount INTEGER)''')
    
    # Таблица рефералов
    c.execute('''CREATE TABLE IF NOT EXISTS referrals
                (referrer_id INTEGER, referred_id INTEGER)''')
    
    conn.commit()
    conn.close()

# === Функции работы с данными ===
def generate_ref_code():
    return str(uuid.uuid4())[:8]

def get_player(user_id):
    conn = sqlite3.connect('crypto_tycoon.db')
    c = conn.cursor()
    
    # Основная информация
    c.execute("SELECT * FROM players WHERE user_id=?", (user_id,))
    data = c.fetchone()
    
    if not data:
        return None
        
    player = {
        "user_id": data[0],
        "balance": data[1],
        "mining_rigs": data[2],
        "bitcoin_balance": data[3],
        "day": data[4],
        "quest_progress": data[5],
        "ref_code": data[6],
        "shares": {}
    }
    
    # Акции
    for company in SHARE_PRICES:
        c.execute(f"SELECT amount FROM shares_{company.lower().replace(' ', '_')} WHERE user_id=?", (user_id,))
        share_data = c.fetchone()
        player["shares"][company] = share_data[0] if share_data else 0
    
    conn.close()
    return player

def save_player(player):
    conn = sqlite3.connect('crypto_tycoon.db')
    c = conn.cursor()
    
    # Основная информация
    c.execute("""INSERT OR REPLACE INTO players 
                 (user_id, balance, mining_rigs, bitcoin_balance, day, quest_progress, ref_code)
                 VALUES (?, ?, ?, ?, ?, ?, ?)""",
              (player["user_id"],
               player["balance"],
               player["mining_rigs"],
               player["bitcoin_balance"],
               player["day"],
               player["quest_progress"],
               player["ref_code"]))
    
    # Акции
    for company, amount in player["shares"].items():
        table_name = f"shares_{company.lower().replace(' ', '_')}"
        c.execute(f"CREATE TABLE IF NOT EXISTS {table_name} (user_id INTEGER PRIMARY KEY, amount INTEGER)")
        c.execute(f"INSERT OR REPLACE INTO {table_name} (user_id, amount) VALUES (?, ?)",
                 (player["user_id"], amount))
    
    conn.commit()
    conn.close()

# === Реферальная система ===
def get_referral_count(user_id):
    conn = sqlite3.connect('crypto_tycoon.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

# === Квестовая система ===
def check_quests(player):
    """Проверяет выполнение квестов"""
    if player["quest_progress"] < len(QUESTS):
        return QUESTS[player["quest_progress"]]["condition"](player)
    return False

# === Команды бота ===
def start(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    
    # Обработка реферальной ссылки
    if context.args and len(context.args) > 0:
        referrer_id = context.args[0]
        conn = sqlite3.connect('crypto_tycoon.db')
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO referrals (referrer_id, referred_id) VALUES (?, ?)",
                 (referrer_id, user_id))
        conn.commit()
        conn.close()
        
        context.bot.send_message(
            chat_id=referrer_id,
            text="🎉 Пользователь зарегистрировался по вашей ссылке! Вы получили $500 бонуса!"
        )
    
    player = get_player(user_id)
    if not player:
        player = {
            "user_id": user_id,
            "balance": 5000,
            "mining_rigs": 0,
            "bitcoin_balance": 0,
            "day": 1,
            "quest_progress": 0,
            "ref_code": generate_ref_code(),
            "shares": {company: 0 for company in SHARE_PRICES}
        }
        save_player(player)
        update.message.reply_text(
            "🎮 Добро пожаловать в Crypto Tycoon!\n"
            "Пройдите квесты, чтобы получить дополнительные бонусы!\n"
            "Используйте /quest для просмотра задания"
        )
    else:
        update.message.reply_text("Вы уже в игре! Используйте /quest для просмотра заданий")

def next_day(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    player = get_player(user_id)
    
    if not player:
        return
    
    current_quest = QUESTS[player["quest_progress"]]
    
    # Проверка выполнения квеста
    if not current_quest["condition"](player):
        update.message.reply_text("❌ Сначала выполните текущее задание!")
        return
    
    # Получение награды за квест
    player["balance"] += current_quest["reward"]
    player["quest_progress"] += 1
    
    # Генерация дохода
    income = player["mining_rigs"] * MINING_INCOME
    player["balance"] += income
    player["day"] += 1
    
    update_prices()
    save_player(player)
    
    update.message.reply_text(
        f"📅 День {player['day']}\n"
        f"✔ Вы выполнили задание: {current_quest['name']}! Получено: ${current_quest['reward']}\n"
        f"⛏ Майнинг принес ${income}\n"
        f"💰 Ваш баланс: ${player['balance']}"
    )

def update_prices():
    """Обновляет цены на акции"""
    date = datetime.now().strftime("%Y-%m-%d")
    
    for company in SHARE_PRICES:
        change = random.uniform(-0.2, 0.3)
        new_price = max(50, int(SHARE_PRICES[company] * (1 + change)))
        SHARE_PRICES[company] = new_price
        
        conn = sqlite3.connect('crypto_tycoon.db')
        c = conn.cursor()
        table_name = f"{company.lower().replace(' ', '_')}_history"
        c.execute(f"CREATE TABLE IF NOT EXISTS {table_name} (date TEXT, price REAL)")
        c.execute(f"INSERT INTO {table_name} (date, price) VALUES (?, ?)", (date, new_price))
        conn.commit()
        conn.close()

def info(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    player = get_player(user_id)
    
    if not player:
        return
    
    income = player["mining_rigs"] * MINING_INCOME
    stock_value = sum(
        count * SHARE_PRICES[company] 
        for company, count in player["shares"].items()
    )
    
    shares_info = "\n".join(
        f"{company}: {count} акций (${SHARE_PRICES[company]}/шт)" 
        for company, count in player["shares"].items() if count > 0
    )
    
    update.message.reply_text(
        f"📊 Ваш статус:\n"
        f"День: {player['day']}\n"
        f"Баланс: ${player['balance']}\n"
        f"Майнинг-фермы: {player['mining_rigs']} шт\n"
        f"Доход в день: ${income}\n"
        f"Стоимость ваших активов: ${stock_value}"
    )

def buy_rig(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    player = get_player(user_id)
    
    if not player or len(context.args) != 1:
        update.message.reply_text("Используйте: /buy_rig [количество]")
        return
    
    try:
        count = int(context.args[0])
        cost = MINING_COST * count
        
        if player["mining_rigs"] + count > MAX_MINING_RIGS:
            update.message.reply_text(f"❌ Максимум {MAX_MINING_RIGS} ферм")
            return
            
        if player["balance"] >= cost:
            player["balance"] -= cost
            player["mining_rigs"] += count
            save_player(player)
            update.message.reply_text(f"✅ Куплено {count} майнинг-ферм за ${cost}")
        else:
            update.message.reply_text("❌ Недостаточно средств")
    except:
        update.message.reply_text("Используйте: /buy_rig [количество]")

def buy_share(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    player = get_player(user_id)
    
    if not player or len(context.args) != 2:
        update.message.reply_text("Используйте: /buy_share [компания] [количество]")
        return
    
    company, count = context.args[0], int(context.args[1])
    if company not in SHARE_PRICES:
        update.message.reply_text("❌ Неверное название компании")
        return
        
    price = SHARE_PRICES[company] * count
    if player["balance"] >= price:
        player["balance"] -= price
        player["shares"][company] += count
        save_player(player)
        update.message.reply_text(f"📈 Куплено {count} акций {company} за ${price}")
    else:
        update.message.reply_text("❌ Недостаточно средств")

def sell_share(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    player = get_player(user_id)
    
    if not player or len(context.args) != 2:
        update.message.reply_text("Используйте: /sell_share [компания] [количество]")
        return
    
    company, count = context.args[0], int(context.args[1])
    if company not in SHARE_PRICES:
        update.message.reply_text("❌ Нет такой компании")
        return
        
    if player["shares"].get(company, 0) >= count:
        price = SHARE_PRICES[company] * count
        player["balance"] += price
        player["shares"][company] -= count
        save_player(player)
        update.message.reply_text(f"📉 Продано {count} акций {company} за ${price}")
    else:
        update.message.reply_text("❌ Недостаточно акций")

def quest(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    player = get_player(user_id)
    
    if not player:
        return
    
    if player["quest_progress"] >= len(QUESTS):
        update.message.reply_text("🏆 Все квесты завершены!")
        return
    
    current_quest = QUESTS[player["quest_progress"]]
    status = "✅" if current_quest["condition"](player) else "❌"
    
    update.message.reply_text(
        f"🎯 Текущий квест ({player['quest_progress'] + 1}/{len(QUESTS)}):\n"
        f"Название: {current_quest['name']}\n"
        f"Описание: {current_quest['description']}\n"
        f"Статус: {status}\n"
        f"Награда: ${current_quest['reward']}"
    )

def referral(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    player = get_player(user_id)
    
    if not player:
        return
    
    count = get_referral_count(user_id)
    update.message.reply_text(
        f"🎁 Реферальная система:\n"
        f"Приглашайте друзей и получайте $500 за каждого!\n"
        f"Ваша реферальная ссылка: https://t.me/CryptoTycoonBot?start={player['ref_code']}\n"
        f"Приглашено: {count}/3\n"
        f"Награды: +{count * 500} CC"
    )

def graph(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    player = get_player(user_id)
    
    if len(context.args) != 1:
        update.message.reply_text("Используйте: /graph [компания]")
        return
    
    company = context.args[0]
    if company not in SHARE_PRICES:
        update.message.reply_text("❌ Нет такой компании")
        return
    
    # Здесь должна быть логика построения графика
    update.message.reply_text(f"📊 История цен на {company} за неделю")

# === Основные функции ===
def main():
    init_db()
    updater = Updater(os.getenv("TELEGRAM_BOT_TOKEN"), use_context=True)
    dp = updater.dispatcher

    # Добавьте команды
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("next_day", next_day))
    dp.add_handler(CommandHandler("info", info))
    dp.add_handler(CommandHandler("buy_rig", buy_rig))
    dp.add_handler(CommandHandler("buy_share", buy_share))
    dp.add_handler(CommandHandler("sell_share", sell_share))
    dp.add_handler(CommandHandler("quest", quest))
    dp.add_handler(CommandHandler("referral", referral))
    dp.add_handler(CommandHandler("graph", graph))

    updater.start_polling()
    updater.idle()
