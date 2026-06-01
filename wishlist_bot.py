"""
Telegram Wishlist Bot
=====================
Команды:
  /start  — приветствие
  /help   — список команд
  /add    — добавить желание
  /list   — показать вишлист
  /remove — удалить желание по номеру
  /clear  — очистить вишлист

Запуск:
  pip install python-telegram-bot
  BOT_TOKEN=ваш_токен python wishlist_bot.py
"""

import os
import json
import logging
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, ContextTypes, filters
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)

# Файл для хранения данных (JSON)
DATA_FILE = Path("wishlist_data.json")

# Состояния диалога
WAITING_FOR_ITEM = 1


# ─── Хранилище ────────────────────────────────────────────────────────────────

def load_data() -> dict:
    if DATA_FILE.exists():
        with DATA_FILE.open(encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_data(data: dict) -> None:
    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_wishlist(user_id: int) -> list:
    data = load_data()
    return data.get(str(user_id), [])


def set_wishlist(user_id: int, items: list) -> None:
    data = load_data()
    data[str(user_id)] = items
    save_data(data)


# ─── Вспомогательные ──────────────────────────────────────────────────────────

def format_list(items: list) -> str:
    if not items:
        return "Твой вишлист пуст 🤷\nДобавь что-нибудь командой /add"
    lines = []
    for i, item in enumerate(items, 1):
        name = item["name"]
        price = item.get("price")
        line = f"{i}. {name}"
        if price:
            line += f" — {price}"
        lines.append(line)
    return "🎁 *Твой вишлист:*\n\n" + "\n".join(lines)


def delete_keyboard(items: list) -> InlineKeyboardMarkup:
    """Инлайн-клавиатура для удаления конкретного элемента."""
    buttons = []
    for i, item in enumerate(items):
        label = f"❌ {i+1}. {item['name']}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"del_{i}")])
    buttons.append([InlineKeyboardButton("← Назад", callback_data="cancel_del")])
    return InlineKeyboardMarkup(buttons)


# ─── Обработчики команд ───────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    name = update.effective_user.first_name
    await update.message.reply_text(
        f"Привет, {name}! 👋\n\n"
        "Я помогу вести твой *вишлист* — список желаний.\n\n"
        "📋 /list — показать список\n"
        "➕ /add — добавить желание\n"
        "🗑 /remove — удалить желание\n"
        "💥 /clear — очистить всё\n"
        "❓ /help — помощь",
        parse_mode="Markdown"
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "*Команды бота:*\n\n"
        "/add — добавить желание в список\n"
        "  Формат: `Название` или `Название — цена`\n"
        "  Пример: `AirPods Pro — 20 000 ₽`\n\n"
        "/list — посмотреть весь вишлист\n\n"
        "/remove — удалить позицию из списка\n\n"
        "/clear — очистить список полностью",
        parse_mode="Markdown"
    )


async def cmd_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    items = get_wishlist(update.effective_user.id)
    await update.message.reply_text(format_list(items), parse_mode="Markdown")


async def cmd_add_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Напиши название желания.\n"
        "Можно добавить цену через ` — `\n\n"
        "_Пример:_ `iPhone 16 Pro — 130 000 ₽`\n\n"
        "Или /cancel чтобы отменить.",
        parse_mode="Markdown"
    )
    return WAITING_FOR_ITEM


async def cmd_add_receive(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if " — " in text:
        name, price = text.split(" — ", 1)
        name, price = name.strip(), price.strip()
    else:
        name, price = text, None

    if not name:
        await update.message.reply_text("Название не может быть пустым. Попробуй ещё раз или /cancel.")
        return WAITING_FOR_ITEM

    uid = update.effective_user.id
    items = get_wishlist(uid)
    items.append({"name": name, "price": price})
    set_wishlist(uid, items)

    msg = f"✅ *{name}*"
    if price:
        msg += f" за *{price}*"
    msg += " добавлен в вишлист!"
    await update.message.reply_text(msg, parse_mode="Markdown")
    return ConversationHandler.END


async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END


async def cmd_remove(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    items = get_wishlist(uid)
    if not items:
        await update.message.reply_text("Вишлист уже пуст 🤷")
        return
    await update.message.reply_text(
        "Что удалить?",
        reply_markup=delete_keyboard(items)
    )


async def callback_delete(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    if query.data == "cancel_del":
        await query.edit_message_text("Отменено.")
        return

    idx = int(query.data.split("_")[1])
    items = get_wishlist(uid)
    if idx < len(items):
        removed = items.pop(idx)
        set_wishlist(uid, items)
        await query.edit_message_text(
            f"🗑 *{removed['name']}* удалён из вишлиста.",
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text("Позиция не найдена.")


async def cmd_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    set_wishlist(uid, [])
    await update.message.reply_text("💥 Вишлист очищен!")


async def unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Не знаю такой команды 🤔\nНапиши /help чтобы увидеть список доступных команд."
    )


# ─── Точка входа ──────────────────────────────────────────────────────────────

def main() -> None:
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("Нужно задать переменную окружения BOT_TOKEN")

    app = ApplicationBuilder().token(token).build()

    # ConversationHandler для команды /add
    add_conv = ConversationHandler(
        entry_points=[CommandHandler("add", cmd_add_start)],
        states={
            WAITING_FOR_ITEM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, cmd_add_receive)
            ]
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("remove", cmd_remove))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(add_conv)
    app.add_handler(CallbackQueryHandler(callback_delete, pattern=r"^(del_\d+|cancel_del)$"))
    app.add_handler(MessageHandler(filters.COMMAND, unknown))

    logging.info("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()