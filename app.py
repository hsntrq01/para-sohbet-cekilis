
import os
import random
import logging
import html
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


def giveaway_text(giveaway):
    return (
        "🎁 ÇEKİLİŞ BAŞLADI!\n\n"
        f"🏆 Ödül: {giveaway['prize']}\n"
        f"👥 Kazanan sayısı: {giveaway['winners_count']}\n"
        f"⏳ Süre: {giveaway['minutes']} dakika\n"
        f"👤 Katılımcı: {len(giveaway['participants'])}\n\n"
        "Katılmak için aşağıdaki butona bas!"
    )


def giveaway_keyboard(giveaway):
    count = len(giveaway["participants"])
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            f"🎉 Çekilişe Katıl ({count})",
            callback_data="join_giveaway",
        )
    ]])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎉 Para Kazandıran Sohbet Çekiliş Botu\n\n"
        "Çekiliş başlatmak için grupta /cekilis yaz."
    )


async def cekilis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        await update.message.reply_text(
            "Bu komutu grubunda kullanmalısın."
        )
        return

    member = await context.bot.get_chat_member(chat.id, user.id)

    if member.status not in ("administrator", "creator"):
        await update.message.reply_text(
            "❌ Yalnızca grup yöneticileri çekiliş başlatabilir."
        )
        return

    if chat.id in active_giveaways:
        await update.message.reply_text(
            "❌ Bu grupta zaten aktif bir çekiliş var."
        )
        return

    args = context.args

    if len(args) < 3:
        await update.message.reply_text(
            "Kullanım: /cekilis 10 1 100 USDT\n"
            "10 = dakika, 1 = kazanan sayısı."
        )
        return

    try:
        minutes = int(args[0])
        winners_count = int(args[1])

        if not 1 <= minutes <= 10080:
            raise ValueError
        if not 1 <= winners_count <= 100:
            raise ValueError

        prize = " ".join(args[2:])

    except ValueError:
        await update.message.reply_text(
            "❌ Süre ve kazanan sayısı geçersiz."
        )
        return

    giveaway = {
        "participants": {},
        "winners_count": winners_count,
        "prize": prize,
        "minutes": minutes,
        "ends_at": datetime.now(timezone.utc)
        + timedelta(minutes=minutes),
    }

    active_giveaways[chat.id] = giveaway

    message = await update.message.reply_text(
        giveaway_text(giveaway),
        reply_markup=giveaway_keyboard(giveaway),
    )

    giveaway["message_id"] = message.message_id

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
        await query.answer(
            "Bu çekiliş artık aktif değil.",
            show_alert=True,
        )
        return

    user = query.from_user

    if user.id in giveaway["participants"]:
        await query.answer(
            "Zaten çekilişe katıldın! 🎉",
            show_alert=True,
        )
        return

    giveaway["participants"][user.id] = {
        "name": user.full_name,
        "username": user.username,
    }

    try:
        await query.edit_message_text(
            text=giveaway_text(giveaway),
            reply_markup=giveaway_keyboard(giveaway),
        )
    except Exception:
        log.exception("Çekiliş mesajı güncellenemedi.")

    await query.answer("Çekilişe katıldın! 🎉")


async def finish_giveaway(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]
    giveaway = active_giveaways.pop(chat_id, None)

    if not giveaway:
        return

    participants = list(giveaway["participants"].items())
    winner_count = min(
        giveaway["winners_count"],
        len(participants),
    )

    if winner_count == 0:
        result = (
            "🎁 ÇEKİLİŞ SONA ERDİ!\n\n"
            f"🏆 Ödül: {html.escape(giveaway['prize'])}\n"
            "Katılımcı olmadığı için kazanan seçilemedi."
        )
    else:
        winners = random.SystemRandom().sample(
            participants,
            winner_count,
        )

        lines = []

        for index, (user_id, info) in enumerate(winners, 1):
            if info["username"]:
                name = "@" + html.escape(info["username"])
            else:
                safe_name = html.escape(info["name"])
                name = (
                    f'<a href="tg://user?id={user_id}">'
                    f'{safe_name}</a>'
                )

            lines.append(f"{index}. {name}")

        result = (
            "🎉 ÇEKİLİŞ SONA ERDİ!\n\n"
            f"🏆 Ödül: {html.escape(giveaway['prize'])}\n"
            f"👥 Katılımcı: {len(participants)}\n\n"
            "🏅 KAZANANLAR:\n"
            + "\n".join(lines)
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
        CallbackQueryHandler(
            join_giveaway,
            pattern="^join_giveaway$",
        )
    )

    log.info("Çekiliş botu başlatılıyor.")
    app.run_polling()


if __name__ == "__main__":
    main()
