import os
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
MARKUP_PERCENT = 22

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

user_state = {}
orders = {}
order_id = 1000

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🟢 Купить BTC")],
        [KeyboardButton(text="🔴 Продать BTC")],
        [KeyboardButton(text="👤 Личный кабинет"), KeyboardButton(text="💬 Личный помощник")],
    ],
    resize_keyboard=True
)

async def get_btc_price_rub():
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=rub"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            return float(data["bitcoin"]["rub"])

@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer(
        "👋 Добро пожаловать.\n\n"
        "Я помогу быстро и спокойно обменять рубли на Bitcoin.\n\n"
        "Что хотите сделать?",
        reply_markup=main_menu
    )

@dp.message(F.text == "🟢 Купить BTC")
async def buy_btc(message: types.Message):
    user_state[message.from_user.id] = {"step": "buy_amount"}
    await message.answer(
        "🟢 Купить Bitcoin\n\n"
        "Сколько рублей хотите обменять?\n\n"
        "Например:\n"
        "10000"
    )

@dp.message(F.text.regexp(r"^\d+([.,]\d+)?$"))
async def amount_handler(message: types.Message):
    global order_id

    user_id = message.from_user.id
    state = user_state.get(user_id)

    if not state:
        await message.answer("Выберите действие в меню.")
        return

    if state["step"] == "buy_amount":
        amount_rub = float(message.text.replace(",", "."))
        btc_price = await get_btc_price_rub()

        pay_amount = round(amount_rub * (1 + MARKUP_PERCENT / 100))
        btc_amount = amount_rub / btc_price

        state.update({
            "amount_rub": amount_rub,
            "pay_amount": pay_amount,
            "btc_price": btc_price,
            "btc_amount": btc_amount,
            "step": "btc_address"
        })

        await message.answer(
            "Отлично 👍\n\n"
            "Вы получите:\n"
            f"{btc_amount:.8f} BTC\n\n"
            "К оплате:\n"
            f"{pay_amount:,.0f} ₽\n\n"
            "⏱ Курс фиксируется на 15 минут.\n\n"
            "Теперь отправьте BTC-кошелёк, куда перевести Bitcoin."
        )

@dp.message()
async def text_handler(message: types.Message):
    global order_id

    user_id = message.from_user.id
    state = user_state.get(user_id)

    if not state:
        if message.text == "👤 Личный кабинет":
            await message.answer(
                "👤 Личный кабинет\n\n"
                "💳 RUB-кошелёк: 0 ₽\n"
                "₿ BTC-кошелёк: 0.00000000 BTC\n"
                "🎁 Бонусы: 0 ₽\n\n"
                "Личный кабинет добавим следующим этапом."
            )
        elif message.text == "💬 Личный помощник":
            await message.answer("Напишите ваш вопрос. Помощник скоро ответит.")
        elif message.text == "🔴 Продать BTC":
            await message.answer("Продажу BTC добавим следующим этапом.")
        else:
            await message.answer("Выберите действие кнопкой в меню.")
        return

    if state["step"] == "btc_address":
        btc_address = message.text.strip()
        order_id += 1

        orders[order_id] = {
            "user_id": user_id,
            "username": message.from_user.username,
            "name": message.from_user.full_name,
            "btc_address": btc_address,
            **state
        }

        user_state.pop(user_id, None)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Отправить реквизиты", callback_data=f"send_requisites:{order_id}")],
            [InlineKeyboardButton(text="💬 Написать клиенту", callback_data=f"reply:{order_id}")],
            [InlineKeyboardButton(text="✅ Выполнено", callback_data=f"done:{order_id}")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel:{order_id}")],
        ])

        await message.answer(
            "✅ Операция создана\n\n"
            f"Номер: BTC-{order_id}\n\n"
            "Скоро отправим реквизиты для оплаты."
        )

        await bot.send_message(
            ADMIN_ID,
            "🟡 Новая операция\n\n"
            f"Номер: BTC-{order_id}\n"
            "Тип: Купить BTC\n\n"
            f"Клиент: {message.from_user.full_name}\n"
            f"Username: @{message.from_user.username if message.from_user.username else 'нет'}\n"
            f"ID: {user_id}\n\n"
            f"Получит: {state['btc_amount']:.8f} BTC\n"
            f"К оплате: {state['pay_amount']:,.0f} ₽\n"
            f"BTC-кошелёк:\n{btc_address}",
            reply_markup=keyboard
        )

@dp.callback_query(F.data.startswith("send_requisites:"))
async def send_requisites(callback: types.CallbackQuery):
    oid = int(callback.data.split(":")[1])
    user_state[callback.from_user.id] = {"step": "admin_requisites", "order_id": oid}
    await callback.message.answer(
        f"Введите реквизиты для операции BTC-{oid}.\n\n"
        "Можно отправить текстом: банк, имя, телефон, сумма."
    )
    await callback.answer()

@dp.message()
async def admin_requisites_handler(message: types.Message):
    state = user_state.get(message.from_user.id)
    if not state or state.get("step") != "admin_requisites":
        return

    oid = state["order_id"]
    order = orders.get(oid)

    if not order:
        await message.answer("Операция не найдена.")
        return

    user_state.pop(message.from_user.id, None)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"paid:{oid}")],
        [InlineKeyboardButton(text="💬 Написать помощнику", callback_data=f"client_help:{oid}")]
    ])

    await bot.send_message(
        order["user_id"],
        "💳 Реквизиты для оплаты\n\n"
        f"{message.text}\n\n"
        "После оплаты нажмите кнопку ниже.",
        reply_markup=keyboard
    )

    await message.answer(f"✅ Реквизиты отправлены клиенту по операции BTC-{oid}.")

@dp.callback_query(F.data.startswith("paid:"))
async def client_paid(callback: types.CallbackQuery):
    oid = int(callback.data.split(":")[1])
    order = orders.get(oid)

    await callback.message.answer(
        "Спасибо ❤️\n\n"
        "Мы получили уведомление об оплате.\n"
        "Проверяем перевод."
    )

    await bot.send_message(
        ADMIN_ID,
        f"🔔 Клиент сообщил об оплате\n\nОперация BTC-{oid}\n\nПроверь поступление денег."
    )
    await callback.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
