import os
import asyncio
import subprocess
import tempfile
from pathlib import Path

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


def edit_video(input_file: str, output_file: str):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    command = [
        ffmpeg,
        "-y",
        "-i", input_file,

        "-vf",
        (
            "scale=1280:720:force_original_aspect_ratio=increase,"
            "crop=1280:720,"
            "eq=contrast=1.12:brightness=0.02:saturation=1.12,"
            "unsharp=5:5:0.7:5:5:0,"
            "vignette=PI/5"
        ),

        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",

        "-c:a", "aac",
        "-b:a", "128k",

        "-movflags", "+faststart",
        output_file,
    ]

    subprocess.run(
        command,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔥 Madrid Era Editor آماده است!\n\n"
        "ویدیوت رو بفرست تا ادیتش کنم."
    )


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    if not message.video and not message.document:
        return

    status = await message.reply_text("🎬 دارم ویدیو رو ادیت می‌کنم...")

    input_path = None
    output_path = None

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)

            input_path = temp_dir / "input.mp4"
            output_path = temp_dir / "madrid_era_edit.mp4"

            if message.video:
                file = await message.video.get_file()
            else:
                file = await message.document.get_file()

            await file.download_to_drive(str(input_path))

            loop = asyncio.get_running_loop()

            await loop.run_in_executor(
                None,
                edit_video,
                str(input_path),
                str(output_path),
            )

            await status.edit_text("✅ ادیت آماده شد! در حال ارسال...")

            with open(output_path, "rb") as video_file:
                await message.reply_video(
                    video=video_file,
                    caption="🔥 Madrid Era Edit"
                )

            await status.delete()

    except Exception as e:
        print("ERROR:", repr(e))
        await status.edit_text(
            "❌ موقع ادیت ویدیو خطا پیش آمد.\n"
            "لاگ Railway را بررسی می‌کنیم."
        )


def main():
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(lambda application: application.bot.delete_webhook(drop_pending_updates=True))
        .build()
    )

    app.add_handler(CommandHandler("start", start))

    app.add_handler(
        MessageHandler(
            filters.VIDEO | filters.Document.VIDEO,
            handle_video
        )
    )

    print("MADRID ERA BOT1 IS RUNNING...")

    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )


if __name__ == "__main__":
    main()
