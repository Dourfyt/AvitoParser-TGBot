from telebot import types
import telebot
import re
import configparser
import sqlite3
from time import sleep

connection = sqlite3.connect('users.db',check_same_thread=False)
cursor=connection.cursor()

# СОЗДАНИЕ БД НЕ ТРОГАТЬ!!!
cursor.execute('''
CREATE TABLE IF NOT EXISTS Users (
phone TEXT PRIMARY KEY,
chat_id INTEGER NULL
)
''')
cursor.execute('''
CREATE TABLE IF NOT EXISTS URLS (
id INTEGER PRIMARY KEY,
URL TEXT NULL UNIQUE
)
''')
connection.commit()
connection.close()


API_TOKEN = '6626481813:AAGBT99QgG28pFslXoSy9RgquKx99kg5C6w'
bot = telebot.TeleBot(API_TOKEN)

@bot.message_handler(commands=['start'])
def handle_start(message):
    config = configparser.ConfigParser(interpolation=None)
    config.read("settings.ini")
    admins = [admin.strip() for admin in config["Avito"]["Admins"].split(",")]
    if str(message.chat.id) in admins:
        markup = types.InlineKeyboardMarkup()
        button1 = types.InlineKeyboardButton('Добавить пользователя', callback_data='add_client')
        button2 = types.InlineKeyboardButton('Удалить пользователя', callback_data='remove_client')
        button3 = types.InlineKeyboardButton('Добавить ссылку', callback_data='add_url')
        button4 = types.InlineKeyboardButton('Удалить ссылку', callback_data='remove_url')
        markup.add(button1, button2, button3, button4)
        bot.send_message(message.chat.id, "Привет, я админ-панель!", reply_markup=markup)
    else:
        keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True) #Подключаем клавиатуру
        button_phone = types.KeyboardButton(text="Отправить телефон", request_contact=True) #Указываем название кнопки, которая появится у пользователя
        keyboard.add(button_phone) #Добавляем эту кнопку
        bot.send_message(message.chat.id, 'Номер телефона', reply_markup=keyboard) #Дублируем сообщением о том, что пользователь сейчас отправит боту свой номер телефона (на всякий случай, но это не обязательно)
    

@bot.callback_query_handler(func=lambda call: True) 
def add_or_remove_client_urls(call):
    if call.data=="add_client":
        msg = bot.send_message(call.message.chat.id, "Введите номер телефона пользователя в формате 79000000000")
        bot.register_next_step_handler(msg, add_client)
    elif call.data=='remove_client':
        connection = sqlite3.connect('users.db',check_same_thread=False)
        cursor=connection.cursor()
        cursor.execute('SELECT rowid,phone FROM Users ORDER BY rowid')
        results = cursor.fetchall()
        bot.send_message(call.message.chat.id, "Вот список всех пользователей:")
        for row in results:
            bot.send_message(call.message.chat.id, f'{row[0]}. {row[1]}')
        msg = bot.send_message(call.message.chat.id, "Введите номер для удаления:")
        bot.register_next_step_handler(msg, remove_client)
    elif call.data == "add_url":
        msg = bot.send_message(call.message.chat.id, "Введите ссылку с поиском на авито в формате https://www.avito.ru/тут_дальше_текст")
        bot.register_next_step_handler(msg, add_url)
    elif call.data == "remove_url":
        connection = sqlite3.connect('users.db',check_same_thread=False)
        cursor=connection.cursor()
        cursor.execute('SELECT rowid,URL FROM URLS ORDER BY rowid')
        results = cursor.fetchall()
        bot.send_message(call.message.chat.id, "Вот список обрабатываемых ссылок:")
        for row in results:
            bot.send_message(call.message.chat.id, f'{row[0]}. {row[1]}')
        msg = bot.send_message(call.message.chat.id, "Введите номер для удаления:")
        bot.register_next_step_handler(msg, remove_url)

def add_client(message):
    try:
        match = re.match(r"^7\d{10}$", message.text)
        if match:
            connection = sqlite3.connect('users.db',check_same_thread=False)
            cursor=connection.cursor()
            cursor.execute('''INSERT OR IGNORE INTO Users (phone) VALUES (?)''', (message.text,))
            connection.commit()
            connection.close()
            bot.send_message(message.chat.id, "Успешно, теперь пользователь должен авторизоваться в этом боте!")
        else:
            bot.send_message(message.chat.id, "Вы ввели неправильный формат, попробуйте еще раз!")
            bot.register_next_step_handler(message, add_client)
    except:
        bot.send_message(message.chat.id, 'Что-то пошло не так, попробуйте еще раз или напишите администратору')

def remove_client(message):
    try:
        connection = sqlite3.connect('users.db',check_same_thread=False)
        cursor=connection.cursor()
        cursor.execute('DELETE FROM Users WHERE rowid = ?', (message.text,))
        connection.commit()
        connection.close()
        bot.send_message(message.chat.id, "Успешно!")
    except:
        bot.send_message(message.chat.id, 'Что-то пошло не так, попробуйте еще раз или напишите администратору')

def add_url(message):
    try:
        match = re.match(r"^(https:\/\/www.avito.ru\/)+", message.text)
        if match:
            connection = sqlite3.connect('users.db',check_same_thread=False)
            cursor=connection.cursor()
            cursor.execute('''INSERT OR IGNORE INTO URLS (URL) VALUES (?)''', (message.text,))
            connection.commit()
            connection.close()
            bot.send_message(message.chat.id, "Успешно!")
        else:
            bot.send_message(message.chat.id, "Вы ввели неправильный формат, попробуйте еще раз!")
            bot.register_next_step_handler(message, add_url)
    except:
        bot.send_message(message.chat.id, 'Что-то пошло не так, попробуйте еще раз или напишите администратору')


def remove_url(message):
    try:
        connection = sqlite3.connect('users.db',check_same_thread=False)
        cursor=connection.cursor()
        cursor.execute('DELETE FROM URLS WHERE rowid = ?', (message.text,))
        connection.commit()
        connection.close()
        bot.send_message(message.chat.id, "Успешно!")
    except:
        bot.send_message(message.chat.id, 'Что-то пошло не так, попробуйте еще раз или напишите администратору')


@bot.message_handler(content_types=['contact'])
def contact(message):
    if message.contact is not None: 
        connection = sqlite3.connect('users.db',check_same_thread=False)
        cursor=connection.cursor()
        phone = message.contact.phone_number
        phones = cursor.execute('SELECT phone FROM Users').fetchall()
        for number in phones:
            if phone == number[0]:
                cursor.execute('UPDATE Users SET chat_id = ? WHERE phone = ?', (message.chat.id, number[0]))
                bot.send_message(message.chat.id, 'Вы успешно авторизованы, теперь вы можете пользоваться ботом @@test_dourfyt_bot')
                connection.commit()
                connection.close()
                return
        bot.send_message(message.chat.id, 'Пользователь не найден, обратитесь к администратору')

while True:
    try:
        bot.polling(none_stop=True)
    except Exception as err:
        print(err)
        print('* Связь оборвана...')
        sleep(15)
        print('* Подключаюсь.')
