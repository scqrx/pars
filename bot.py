import logging
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from database import (
    init_db,
    add_subscription,
    get_user_subscriptions,
    get_all_subscriptions,
    update_subscription,
)
from parser import fetch_product_info

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# каждые 10 минут проверяем цены
CHECK_INTERVAL_SECONDS = 600


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "Привет! Я бот для отслеживания цен на товары.\n\n"
        "Команды:\n"
        "/add <url> — добавить товар по ссылке\n"
        "/list — показать список отслеживаемых товаров\n"
    )
    await update.message.reply_text(text)


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Добавить товар в отслеживание: /add <url>"""
    if not context.args:
        await update.message.reply_text(
            "Пришли ссылку на товар так: /add https://example.com/item"
        )
        return

    url = context.args[0].strip()
    user_id = update.effective_user.id

    await update.message.reply_text("Пробую получить информацию о товаре...")

    try:
        title, price = await fetch_product_info(url)
    except Exception as e:
        logger.exception("Ошибка при парсинге товара")
        await update.message.reply_text(f"Не удалось получить данные по ссылке: {e}")
        return

    add_subscription(user_id=user_id, url=url, title=title, last_price=price)

    msg = "Товар добавлен в отслеживание.\n"
    if title:
        msg += f"Название: {title}\n"
    if price is not None:
        msg += f"Текущая цена: {price} ₽"
    else:
        msg += "Цену определить не удалось, но я буду пытаться при следующей проверке."
    await update.message.reply_text(msg)


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать список отслеживаемых товаров пользователя."""
    user_id = update.effective_user.id
    subs = get_user_subscriptions(user_id)

    if not subs:
        await update.message.reply_text(
            "Ты пока не добавил ни одного товара. Используй /add <url>."
        )
        return

    lines = []
    for sub in subs:
        sub_id, url, title, last_price = sub
        title_part = title or "без названия"
        price_part = f"{last_price} ₽" if last_price is not None else "неизвестна"
        lines.append(f"{sub_id}. {title_part}\n   {url}\n   Цена: {price_part}")

    await update.message.reply_text("Твои товары:\n\n" + "\n\n".join(lines))


async def check_prices_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Периодически проверяет цены всех товаров и шлёт уведомления при изменении."""
    all_subs = get_all_subscriptions()
    if not all_subs:
        return

    logger.info("Запускаем проверку %d подписок", len(all_subs))

    for sub in all_subs:
        sub_id, user_id, url, title, last_price = sub
        try:
            new_title, new_price = await fetch_product_info(url)
        except Exception:
            logger.exception("Ошибка при обновлении товара %s", url)
            continue

        if new_price is None:
            # цену не смогли вытащить — ничего не делаем
            continue

        if not title and new_title:
            title = new_title

        # если в базе цены ещё не было — просто записываем
        if last_price is None:
            update_subscription(sub_id, title=title, last_price=new_price)
            continue

        # если цена изменилась — обновляем и шлём уведомление
        if new_price != last_price:
            update_subscription(sub_id, title=title, last_price=new_price)
            diff = new_price - last_price
            sign = "подорожал" if diff > 0 else "подешевел"
            diff_abs = abs(diff)
            text = (
                f"Цена изменилась для товара:\n"
                f"{title or url}\n\n"
                f"Было: {last_price} ₽\n"
                f"Стало: {new_price} ₽\n"
                f"Товар {sign} на {diff_abs} ₽"
            )
            try:
                await context.bot.send_message(chat_id=user_id, text=text)
            except Exception:
                logger.exception(
                    "Не удалось отправить сообщение пользователю %s", user_id
                )


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("Не задан BOT_TOKEN в .env")

    # создаём БД и таблицу
    init_db()

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CommandHandler("list", list_command))

    # периодическая задача проверки цен
    application.job_queue.run_repeating(
        check_prices_job, interval=CHECK_INTERVAL_SECONDS, first=30
    )

    logger.info("Бот запущен. Ожидаем сообщения...")
    application.run_polling()


if __name__ == "__main__":
    main()
