import logging
import asyncpg
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
import asyncio
from geopy.geocoders import Nominatim

BOT_API_TOKEN = '7227222573:AAF6EY-X_0kDAJn37k1SvMEi0sRbfsHMfTs' # @finding_location_bot
POSTGRES_DATABASE_URL = 'postgresql://postgres:root@localhost:5432/location_db'

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
geolocator = Nominatim(user_agent="geoapiExercises")

async def create_db_pool():
    return await asyncpg.create_pool(POSTGRES_DATABASE_URL)

db_pool = asyncio.get_event_loop().run_until_complete(create_db_pool())

class LocationStates(StatesGroup):
    waiting_for_contact = State()
    waiting_for_location = State()

def get_address(latitude, longitude):
    location = geolocator.reverse(f"{latitude}, {longitude}")
    return location.address if location else "Noma'lum joylashuv."

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    user_id = message.from_user.id
    
    async with db_pool.acquire() as connection:
        query = 'SELECT * FROM users WHERE user_tg_id = $1'
        user = await connection.fetchrow(query, user_id)
    
    if user:
        await message.reply(f"Assalomu alaykum {message.from_user.first_name} {message.from_user.last_name}")
        await message.reply("Iltimos, jonli joylashuvni ulashing.")
        await LocationStates.waiting_for_location.set()
    else:
        contact_button = KeyboardButton('Kontakt ulashish', request_contact=True)
        contact_keyboard = ReplyKeyboardMarkup(resize_keyboard=True).add(contact_button)
        await message.reply(
            "Assalomu alaykum. Sizni ko'rib turganimizdan hursandmiz. "
            "Iltimos, kontakt ulashing.", 
            reply_markup=contact_keyboard
        )
        await LocationStates.waiting_for_contact.set()

@dp.message_handler(content_types=['contact'], state=LocationStates.waiting_for_contact)
async def process_contact(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    full_name = f"{message.contact.first_name} {message.contact.last_name}"
    phone_number = message.contact.phone_number
    
    async with db_pool.acquire() as connection:
        await connection.execute('''
            INSERT INTO users (user_tg_id, full_name, phone_number) VALUES ($1, $2, $3);''', 
            user_id, full_name, phone_number)

    await message.reply("Rahmat! Endi jonli joylashuvni ulashing.")
    await LocationStates.waiting_for_location.set()

@dp.message_handler(content_types=['location'], state=LocationStates.waiting_for_location)
async def process_location(message: types.Message, state: FSMContext):
    if message.location.live_period:
        user_id = message.from_user.id
        start_location = get_address(message.location.latitude, message.location.longitude)
        
        async with db_pool.acquire() as connection:
            query = '''INSERT INTO locations (user_id, start_location, current_location) VALUES ($1, $2, $2)'''
            await connection.execute(query, user_id, start_location)
        
        await message.reply("Sizning boshlang'ich joylashuvingiz aniqlandi.")
        await state.finish()
        asyncio.create_task(update_current_location(user_id))

        arrived_button = KeyboardButton('Yetib keldim')
        arrived_keyboard = ReplyKeyboardMarkup(resize_keyboard=True).add(arrived_button)
        msg = "Yetib kelganingizni bildirish uchun 'Yetib keldim' tugmasini bosing."
        await bot.send_message(user_id, msg, reply_markup=arrived_keyboard)
    else:
        await message.reply("Iltimos, jonli joylashuvni ulashing.")

@dp.message_handler(lambda message: message.text == 'Yetib keldim')
async def process_arrived(message: types.Message):
    user_id = message.from_user.id
    
    async with db_pool.acquire() as connection:
        query = '''SELECT current_location FROM locations WHERE user_id = $1 ORDER BY created_at DESC LIMIT 1'''
        user_location = await connection.fetchrow(query, user_id)
        
        if user_location:
            query = '''UPDATE locations SET end_location = $1, updated_at = NOW() WHERE user_id = $2 AND end_location IS NULL'''
            await connection.execute(query, user_location['current_location'], user_id)
        
        await bot.send_message(user_id, "Yetib kelgan manzilingiz aniqlandi.")
        await bot.send_message(user_id, "Adashib qolsangiz yana jonli joylashuvingizni yuboring.")

    await dp.current_state(user=user_id).finish()

async def update_current_location(user_id):
    async with db_pool.acquire() as connection:
        while True:
            selectCurrentLocationQuery = '''SELECT current_location, end_location FROM locations WHERE user_id = $1 ORDER BY created_at DESC LIMIT 1'''
            location = await connection.fetchrow(selectCurrentLocationQuery, user_id)

            if location and location['end_location'] is not None:
                logging.info(f"User {user_id} has arrived. Stopping location updates.")
                break

            if location:
                current_location = location['current_location']
                logging.info(f"User {user_id} current location: {current_location}")
                await bot.send_message(user_id, f"\tHozirgi joylashuvingiz:\n\n {current_location}")

            await asyncio.sleep(30)

@dp.message_handler(content_types=['location'])
async def update_location(message: types.Message):
    if message.location.live_period:
        user_id = message.from_user.id
        start_location = get_address(message.location.latitude, message.location.longitude)
        
        async with db_pool.acquire() as connection:
            query = '''INSERT INTO locations (user_id, start_location, current_location) VALUES ($1, $2, $2)'''
            await connection.execute(query, user_id, start_location)
        
        await message.reply("Sizning yangi joylashuvingiz aniqlandi")
        asyncio.create_task(update_current_location(user_id))

        arrived_button = KeyboardButton('Yetib keldim')
        arrived_keyboard = ReplyKeyboardMarkup(resize_keyboard=True).add(arrived_button)
        msg = "Yetib kelganingizni bildirish uchun 'Yetib keldim' tugmasini bosing."
        await bot.send_message(user_id, msg, reply_markup=arrived_keyboard)
    else:
        await message.reply("Iltimos, jonli joylashuvni ulashing.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
