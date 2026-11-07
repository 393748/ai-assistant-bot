import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from openai import AsyncOpenAI

# 1. Находим и загружаем файл .env строго из папки со скриптом
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

print("Проверка чтения .env:", BOT_TOKEN)

# Проверка: если токен не подтянулся, сразу пишем понятную ошибку
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден! Убедись, что файл называется именно .env и лежит в папке py.")

# 2. Инициализация клиентов
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
ai_client = AsyncOpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

# 3. Хранилище памяти диалогов, статус VIP
vip_users = {762689848} # Множество для хранения ID VIP-пользователей
user_contexts = {}
FREE_TIER_LIMIT = 3  # Максимальное количество сообщений в истории для бесплатного тарифа
user_balance = {}  # Словарь для хранения баланса пользователей
# 4. Кнопки меню
menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👋 Поздороваться"), KeyboardButton(text="ℹ️ Помощь"), KeyboardButton(text="🤖Разработчик"),KeyboardButton(text="♺Сброс")]
    ],
    resize_keyboard=True
)

# 5. Функция обращения к модели с передачей всей истории
async def ask_ai(messages_history: list) -> str:
    response = await ai_client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=messages_history
    )
    return response.choices[0].message.content


# 6. Команды управления

@dp.message(Command("balance"))
async def balance_handler(message: types.Message):
    user_id = message.from_user.id
    if user_id in vip_users:
        await message.answer("💰 Ваш текущий баланс: неограничен")
        return
    if user_id not in user_balance:
        user_balance[user_id] = FREE_TIER_LIMIT
    current_balance = user_balance[user_id]
    await message.answer(f"💰 Ваш текущий баланс: {current_balance} запросов к ИИ ассистенту")

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user_name = message.from_user.first_name
    text = f"""Привет, {user_name}! 🚀
Я AI-бот с памятью диалога. Напиши мне что-нибудь!

Подсказки по командам:
/reset — сброс контекста
/balance — проверка баланса
/buy — купить запросы (Telegram Stars)
/help — помощь"""

    await message.answer(text, reply_markup=menu_kb)

@dp.message(Command("help"))
async def help_handler(message: types.Message):
    await message.answer("Просто пиши мне сообщения — я помню нить разговора!\nДля сброса памяти используй команду /reset.", reply_markup=menu_kb)

@dp.message(Command("reset"))
async def reset_handler(message: types.Message):
    user_id = message.from_user.id
    user_contexts[user_id] = [
        {"role": "system", "content": "Ты дружелюбный и краткий AI-ассистент в Telegram. Отвечай на русском языке.Так же в самом начале отправь пользователю все команды которые ты можешь обработать."}
    ]
    await message.answer("🧹 Память очищена! Можем начать новую беседу.")

# 7. Обработчики кнопок
@dp.message(F.text == "👋 Поздороваться")
async def hello_handler(message: types.Message):
    await message.answer(f"Здравствуй, {message.from_user.first_name}!")

@dp.message(F.text == "♺Сброс")
async def reset_button_handler(message: types.Message):
    user_id = message.from_user.id
    user_contexts[user_id] = [
        {"role": "system", "content": "Ты дружелюбный и краткий AI-ассистент в Telegram. Отвечай на русском языке."}
    ]
    await message.answer("🧹 Память очищена! Можем начать новую беседу.")
    

@dp.message(F.text == "🤖Разработчик")
async def developer_handler(message: types.Message):
    await message.answer(f"Здравствуй, {message.from_user.first_name}, меня разработал @sgajdisk")


@dp.message(F.text == "ℹ️ Помощь")
async def helping_handler(message: types.Message):
    await message.answer("Задай мне любой вопрос обычным текстом. Чтобы бот забыл прошлый разговор, отправь /reset.")

# 8. Главный обработчик сообщений с поддержкой контекста
@dp.message(F.text)
async def ai_message_handler(message: types.Message):
    # Защита от сообщений без отправителя (убирает ошибку Pylance на from_user)
    if not message.from_user:
        return

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    user_id = message.from_user.id

    # 1. Проверки и списания выполняются ТОЛЬКО для не-VIP
    if user_id not in vip_users:
        # Инициализация новичка (ровно 12 пробелов для действия)
        if user_id not in user_balance:
            user_balance[user_id] = FREE_TIER_LIMIT
        
        # Шлагбаум лимита (return строго внутри условия с 12 пробелами)
        if user_balance[user_id] <= 0:
            await message.answer("Лимит бесплатных запросов исчерпан, оформите подписку")
            return
        
        # Списание (8 пробелов — выполняется, только если лимит > 0)
        user_balance[user_id] -= 1

   # Инициализация истории для нового пользователя
    if user_id not in user_contexts:
        user_contexts[user_id] = [
            {"role": "system", "content": "Ты дружелюбный и краткий AI-ассистент в Telegram. Отвечай на русском языке."}
        ]

    # Добавляем входящее сообщение
    user_contexts[user_id].append({"role": "user", "content": message.text})

    # Ограничение длины контекста (1 системный промпт + до 10 последних сообщений)
    if user_id not in vip_users and len(user_contexts[user_id]) > 11:
        user_contexts[user_id] = [user_contexts[user_id][0]] + user_contexts[user_id][-10:]
    try:
        answer = await ask_ai(user_contexts[user_id])
        # Сохраняем ответ модели в историю
        user_contexts[user_id].append({"role": "assistant", "content": answer})
        await message.answer(answer)
    except Exception as e:
        print(f"!!! Ошибка: {e}")
        await message.answer(f"⚠️ Ошибка: {e}")

# 9. Точка входа
async def main():
    print(">>> AI-Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())