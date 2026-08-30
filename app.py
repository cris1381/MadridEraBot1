import os
import asyncio
import subprocess
import tempfile
from pathlib import Path
import re

import imageio_ffmpeg
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")


FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def run_cmd(command):
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr[-4000:])

    return result


def get_duration(path):
    result = subprocess.run(
        [FFMPEG, "-i", str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    match = re.search(
        r"Duration:\s*(\d+):(\d+):([\d.]+)",
        result.stderr,
    )

    if not match:
        return 15.0

    h = int(match.group(1))
    m = int(match.group(2))
    s = float(match.group(3))

    return h * 3600 + m * 60 + s


def create_edit(video, music, output, instruction):
    duration = get_duration(video)

    # خروجی حداکثر 30 ثانیه و متناسب با ویدیوی ورودی
    if duration <= 10:
        target = duration
    elif duration <= 15:
        target = duration
    elif duration <= 20:
        target = duration
    else:
        target = min(duration, 30)

    # ادیت عمودی مناسب TikTok / Reels
    video_filter = (
        "scale=1080:1920:"
        "force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        "eq=contrast=1.08:"
        "brightness=0.02:"
        "saturation=1.10,"
        "unsharp=5:5:0.55:5:5:0,"
        "vignette=PI/7"
    )

    command = [
        FFMPEG,
        "-y",

        "-i",
        str(video),

        "-stream_loop",
        "-1",

        "-i",
        str(music),

        "-t",
        str(target),

        "-filter:v",
        video_filter,

        "-map",
        "0:v:0",

        "-map",
        "1:a:0",

        "-c:v",
        "libx264",

        "-preset",
        "veryfast",

        "-crf",
        "18",

        "-pix_fmt",
        "yuv420p",

        "-c:a",
        "aac",

        "-b:a",
        "192k",

        "-shortest",

        "-movflags",
        "+faststart",

        str(output),
    ]

    run_cmd(command)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "👑 MADRID ERA CONTROL\n\n"
        "🎬 ویدیو را بفرست.\n"
        "🎵 بعد آهنگ را بفرست.\n"
        "📝 در آخر دستور ادیت را بنویس.\n\n"
        "مثال:\n"
        "ادیت سریع و مدرن، مناسب TikTok"
    )


async def receive_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    if not message.video and not message.document:
        return

    status = await message.reply_text(
        "🎬 ویدیو دریافت شد.\n\n"
        "🎵 حالا آهنگ را بفرست."
    )

    video_path = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".mp4",
    ).name

    try:
        if message.video:
            telegram_file = await message.video.get_file()
        else:
            telegram_file = await message.document.get_file()

        await telegram_file.download_to_drive(video_path)

        context.user_data["video"] = video_path

    except Exception as e:
        print("VIDEO ERROR:", repr(e))

        try:
            os.remove(video_path)
        except:
            pass

        await status.edit_text(
            "❌ دریافت ویدیو ناموفق بود."
        )


async def receive_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    if not message.audio and not message.document:
        return

    if not context.user_data.get("video"):
        await message.reply_text(
            "⚠️ اول ویدیو را بفرست."
        )
        return

    status = await message.reply_text(
        "🎵 دارم آهنگ را دریافت می‌کنم..."
    )

    music_path = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".mp3",
    ).name

    try:
        if message.audio:
            telegram_file = await message.audio.get_file()
        else:
            telegram_file = await message.document.get_file()

        await telegram_file.download_to_drive(music_path)

        context.user_data["music"] = music_path

        await status.edit_text(
            "✅ آهنگ دریافت و ذخیره شد.\n\n"
            "📝 حالا دستور ادیتت را بنویس."
        )

    except Exception as e:
        print("MUSIC ERROR:", repr(e))

        try:
            os.remove(music_path)
        except:
            pass

        await status.edit_text(
            "❌ دریافت آهنگ ناموفق بود."
        )


async def receive_instruction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    instruction = update.message.text.strip()

    video = context.user_data.get("video")
    music = context.user_data.get("music")

    # لینک نمونه فعلاً فقط ذخیره می‌شود
    if instruction.startswith("http://") or instruction.startswith("https://"):
        context.user_data["reference"] = instruction

        await update.message.reply_text(
            "🔗 لینک نمونه دریافت شد.\n\n"
            "📝 حالا دستور ادیت را بنویس."
        )
        return

    if not video:
        await update.message.reply_text(
            "⚠️ اول ویدیو را بفرست."
        )
        return

    if not music:
        await update.message.reply_text(
            "⚠️ اول آهنگ را بفرست."
        )
        return

    status = await update.message.reply_text(
        "🔥 دستور دریافت شد.\n\n"
        "🎬 در حال ساخت ویدیو...\n"
        "⏳ کمی صبر کن."
    )

    output = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".mp4",
    ).name

    try:
        loop = asyncio.get_running_loop()

        await loop.run_in_executor(
            None,
            create_edit,
            video,
            music,
            output,
            instruction,
        )

        await status.edit_text(
            "✅ ادیت آماده شد!\n"
            "📤 در حال ارسال..."
        )

        with open(output, "rb") as video_file:
            await update.message.reply_video(
                video=video_file,
                caption="👑 MADRID ERA EDIT",
                supports_streaming=True,
            )

        await status.delete()

    except Exception as e:
        print("EDIT ERROR:", repr(e))

        await status.edit_text(
            "❌ پردازش انجام نشد.\n"
            "اگر دوباره خطا داد، متن Logs را برایم بفرست."
        )

    finally:
        for path in [video, music, output]:
            if path:
                try:
                    os.remove(path)
                except:
                    pass

        context.user_data.clear()


def main():
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(120)
        .write_timeout(120)
        .pool_timeout(30)
        .build()
    )

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        MessageHandler(
            filters.VIDEO | filters.Document.VIDEO,
            receive_video,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.AUDIO | filters.Document.AUDIO,
            receive_music,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            receive_instruction,
        )
    )

    print("👑 MADRID ERA CONTROL IS RUNNING...")

    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )


if __name__ == "__main__":
    main()
