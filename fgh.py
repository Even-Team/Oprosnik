import json
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackContext,
    CallbackQueryHandler,
    filters
)

# Настройка логгирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = '7826372814:AAHsZi3L2iDZek7gH-fP3V68Z-qVxL-pu0s'
ADMIN_USERNAME = 'Comrade_KIlka'
POLLS_FILE = 'active_polls.json'
ANSWERS_FILE = 'user_answers.json'
USERS_FILE = 'users_data.json'


# Инициализация файлов
def initialize_files():
    for file in [USERS_FILE, POLLS_FILE, ANSWERS_FILE]:
        if not os.path.exists(file):
            with open(file, 'w', encoding='utf-8') as f:
                json.dump({}, f)


def load_json(filename):
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                return json.loads(content) if content else {}
        return {}
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Ошибка чтения {filename}: {e}")
        return {}


def save_json(data, filename):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения {filename}: {e}")


def is_admin(update: Update):
    user = update.effective_user
    return user and user.username == ADMIN_USERNAME


async def start(update: Update, context: CallbackContext):
    try:
        user = update.effective_user
        if not user:
            logger.error("Не удалось получить данные пользователя")
            return

        user_data = {
            'id': user.id,
            'username': user.username or '',
            'first_name': user.first_name or '',
            'last_name': user.last_name or ''
        }

        users = load_json(USERS_FILE)
        users[str(user.id)] = user_data
        save_json(users, USERS_FILE)

        keyboard = [
            [InlineKeyboardButton("Ответить на опрос", callback_data='answer_poll')],
            [InlineKeyboardButton("Помощь", callback_data='help')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "👋 Привет! Я бот для проведения опросов.",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Ошибка в команде start: {e}")


async def new_poll(update: Update, context: CallbackContext):
    try:
        if not is_admin(update):
            await update.message.reply_text("❌ У вас нет прав на создание опросов.")
            return

        await update.message.reply_text("📝 Введите вопрос для нового опроса:")
        context.user_data['state'] = 'awaiting_question'
    except Exception as e:
        logger.error(f"Ошибка в команде new_poll: {e}")


async def broadcast_poll(update: Update, context: CallbackContext):
    try:
        if not is_admin(update):
            return

        users = load_json(USERS_FILE)
        current_poll = load_json(POLLS_FILE)
        if not current_poll:
            await update.callback_query.edit_message_text("Нет активных опросов для рассылки")
            return

        last_poll_id = max(map(int, current_poll.keys())) if current_poll else 0

        keyboard = [
            [InlineKeyboardButton("Ответить", callback_data=f'poll_{last_poll_id}')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        for user_id in users:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"📢 Новый опрос:\n{current_poll[str(last_poll_id)]['question']}",
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.error(f"Не удалось отправить опрос пользователю {user_id}: {e}")

        await update.callback_query.edit_message_text("✅ Опрос разослан всем пользователям!")
    except Exception as e:
        logger.error(f"Ошибка в broadcast_poll: {e}")


async def handle_text(update: Update, context: CallbackContext):
    try:
        if not update.message or not update.message.text:
            return

        if is_admin(update) and context.user_data.get('state') == 'awaiting_question':
            question = update.message.text
            polls = load_json(POLLS_FILE)
            poll_id = len(polls) + 1
            polls[str(poll_id)] = {
                'question': question,
                'active': True
            }
            save_json(polls, POLLS_FILE)
            context.user_data['state'] = None

            keyboard = [
                [InlineKeyboardButton("Разослать опрос", callback_data='broadcast_poll')],
                [InlineKeyboardButton("Отменить", callback_data='cancel_poll')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"✅ Опрос создан:\n{question}\n\nРазослать пользователям?",
                reply_markup=reply_markup
            )
        elif not is_admin(update):
            polls = load_json(POLLS_FILE)
            active_polls = {k: v for k, v in polls.items() if v.get('active')}

            if not active_polls:
                await update.message.reply_text("Сейчас нет активных опросов.")
                return

            last_poll_id = max(map(int, active_polls.keys()))
            user_answer = update.message.text

            answers = load_json(ANSWERS_FILE)
            if str(last_poll_id) not in answers:
                answers[str(last_poll_id)] = {}

            answers[str(last_poll_id)][str(update.effective_user.id)] = user_answer
            save_json(answers, ANSWERS_FILE)

            await update.message.reply_text("✅ Ваш ответ сохранён!")
    except Exception as e:
        logger.error(f"Ошибка в handle_text: {e}")


async def button_handler(update: Update, context: CallbackContext):
    try:
        query = update.callback_query
        await query.answer()

        if query.data == 'answer_poll':
            polls = load_json(POLLS_FILE)
            active_polls = {k: v for k, v in polls.items() if v.get('active')}

            if not active_polls:
                await query.edit_message_text("Сейчас нет активных опросов.")
                return

            last_poll_id = max(map(int, active_polls.keys()))
            await query.edit_message_text(
                f"📝 Текущий опрос:\n{active_polls[str(last_poll_id)]['question']}\n\n"
                "Напишите ваш ответ в чат."
            )

        elif query.data == 'broadcast_poll':
            await broadcast_poll(update, context)

        elif query.data.startswith('poll_'):
            poll_id = query.data.split('_')[1]
            polls = load_json(POLLS_FILE)

            if poll_id not in polls:
                await query.edit_message_text("Этот опрос больше не активен.")
                return

            await query.edit_message_text(
                f"📝 Опрос:\n{polls[poll_id]['question']}\n\n"
                "Напишите ваш ответ в чат."
            )
    except Exception as e:
        logger.error(f"Ошибка в button_handler: {e}")


async def show_results(update: Update, context: CallbackContext):
    try:
        if not is_admin(update):
            await update.message.reply_text("❌ У вас нет прав на просмотр результатов.")
            return

        answers = load_json(ANSWERS_FILE)
        users = load_json(USERS_FILE)

        if not answers:
            await update.message.reply_text("📭 Нет сохранённых ответов.")
            return

        result_text = "📊 Результаты опросов:\n\n"

        for poll_id, user_answers in answers.items():
            polls = load_json(POLLS_FILE)
            question = polls.get(poll_id, {}).get('question', '❓ Неизвестный опрос')

            result_text += f"🔹 {question}\n"

            for user_id, answer in user_answers.items():
                user = users.get(user_id, {})
                username = user.get('username', 'Неизвестный')

                # Безопасное формирование имени
                first_name = user.get('first_name', '') or ''
                last_name = user.get('last_name', '') or ''
                name = f"{first_name} {last_name}".strip()

                result_text += f"👤 @{username} ({name if name else 'Без имени'}): {answer}\n"

            result_text += "\n"

        await update.message.reply_text(result_text)
    except Exception as e:
        logger.error(f"Ошибка в show_results: {e}")


async def end_poll(update: Update, context: CallbackContext):
    try:
        if not is_admin(update):
            await update.message.reply_text("❌ У вас нет прав на завершение опросов.")
            return

        polls = load_json(POLLS_FILE)
        active_polls = {k: v for k, v in polls.items() if v.get('active')}

        if not active_polls:
            await update.message.reply_text("❌ Нет активных опросов.")
            return

        last_poll_id = max(map(int, active_polls.keys()))
        polls[str(last_poll_id)]['active'] = False
        save_json(polls, POLLS_FILE)

        await update.message.reply_text(f"✅ Опрос завершён.")
    except Exception as e:
        logger.error(f"Ошибка в end_poll: {e}")


def main():
    initialize_files()

    application = Application.builder().token(BOT_TOKEN).build()

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("newpoll", new_poll))
    application.add_handler(CommandHandler("results", show_results))
    application.add_handler(CommandHandler("endpoll", end_poll))

    # Обработчики сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Обработчики кнопок
    application.add_handler(CallbackQueryHandler(button_handler))

    application.run_polling()


if __name__ == '__main__':
    main()