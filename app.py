
import os
import random
import logging
from datetime import datetime, timedelta, timezone

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

TOKEN = os.environ["BOT_TOKEN"]
active_giveaways = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎉 Para Kazandıran Sohbet Çekiliş Botu\n\n"
        "Grubunda çekiliş başlatmak için /cekilis komutunu kullan."
    )


async def cekilis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    member = await context.bot.get_chat_member(chat.id, user.id)

    if chat.type == "private":
        await update.message.reply_text(
            "Bu komutu grubunda kullanmalısın."
        )
        return

    if member.status not in ("administrator", "creator"):
        await update.message.reply_text(
            "❌ Yalnızca grup yöneticileri çekiliş başlatabilir."
        )
        return

    if chat.id in active_giveaways:
        await update.message.reply_text(
            "Önce mevcut çekilişin bitmesini bekle."
        )
        return

    # Kullanım: /cekilis 10 1 100 USDT
    # 10 = dakika, 1 = kazanan sayısı, 100 USDT = ödül
    args = context.args
    if len(args) < 4:
        await update.message.reply_text(
            "Kullanım:\n/cekilis 10 1 100 USDT\n\n"
            "Örnek: 10 dakika, 1 kazanan, 100 USDT ödül."
        )
        return

    try:
        minutes = int(args[0])
        winners_count = int(args[1])
        prize = " ".join(args[2:])
        if not 1 <= minutes <= 10080:
            raise ValueError
        if not 1 <= winners_count <= 100:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "Süre ve kazanan sayısı geçerli pozitif sayılar olmalı."
        )
        return

    ends_at = datetime.now(timezone.utc) + timedelta(minutes=minutes)

    active_giveaways[chat.id] = {
        "participants": set(),
        "winners_count": winners_count,
        "prize": prize,
        "ends_at": ends_at,
        "message_id": None,
    }

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "🎉 Çekilişe Katıl (0)",
            callback_data="join_giveaway",
        )
    ]])

    message = await update.message.reply_text(
        f"🎁 ÇEKİLİŞ BAŞLADI!\n\n"
        f"🏆 Ödül: {prize}\n"
        f"👥 Kazanan sayısı: {winners_count}\n"
        f"⏳ Süre: {minutes} dakika\n"
        f"👤 Katılımcı: 0\n\n"
        f"Katılmak için aşağıdaki butona bas!",
        reply_markup=keyboard,
    )

    active_giveaways[chat.id]["message_id"] = message.message_id

    context.job_queue.run_once(
        finish_giveaway,
        when=minutes * 60,
        data={"chat_id": chat.id},
        name=f"giveaway_{chat.id}",
    )


async def join_giveaway(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat.id
    giveaway = active_giveaways.get(chat_id)

    if not giveaway:
        await query.answer("Bu çekiliş aktif değil.", show_alert=True)
        return

    user_id = query.from_user.id

    if user_id in giveaway["participants"]:
        await query.answer("Zaten katıldın! 🎉", show_alert=True)
        return

    giveaway["participants"].add(user_id)
    count = len(giveaway["participants"])

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            f"🎉 Çekilişe Katıl ({count})",
            callback_data="join_giveaway",
        )
    ]])

    await query.edit_message_reply_markup(reply_markup=keyboard)
    await query.answer("Çekilişe katıldın! 🎉")


async def finish_giveaway(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]
    giveaway = active_giveaways.pop(chat_id, None)

    if not giveaway:
        return

    participants = list(giveaway["participants"])
    count = min(giveaway["winners_count"], len(participants))

    if count == 0:
        result = (
            "🎁 ÇEKİLİŞ SONA ERDİ!\n\n"
            f"🏆 Ödül: {giveaway['prize']}\n"
            "Katılımcı olmadığı için kazanan seçilemedi."
        )
    else:
        winners = random.SystemRandom().sample(participants, count)
        lines = []
        for i, user_id in enumerate(winners, 1):
            lines.append(f"{i}. <a href=\"tg://user?id={user_id}\">Kazanan</a>")
        result = (
            "🎉 ÇEKİLİŞ SONA ERDİ!\n\n"
            f"🏆 Ödül: {giveaway['prize']}\n"
            f"👥 Katılımcı: {len(participants)}\n\n"
            "🏅 Kazananlar:\n" + "\n".join(lines)
        )

    await context.bot.send_message(
        chat_id=chat_id,
        text=result,
        parse_mode="HTML",
    )


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cekilis", cekilis))
    app.add_handler(
        CallbackQueryHandler(join_giveaway, pattern="^join_giveaway$")
    )
    log.info("Çekiliş botu başlatılıyor.")
    app.run_polling()


if __name__ == "__main__":
    main()
