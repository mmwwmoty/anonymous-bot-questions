import logging
import sqlite3
import telebot
from telebot import types

# Устанавливаем уровень логгирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Инициализируем бота
bot = telebot.TeleBot('ВАШ БОТ АЙДИ')

# Определение числовых значений для состояний
START = 0
ANONYMOUS = 1
REPLY = 2

# Создаем подключение к базе данных SQLite
def connect_to_database():
    conn = sqlite3.connect('anonaskbot.db')
    cursor = conn.cursor()
    return conn, cursor

# Создаем таблицу для пользователей
def create_users_table(cursor):
    cursor.execute('''CREATE TABLE IF NOT EXISTS users
                      (id INTEGER PRIMARY KEY, username TEXT)''')

# Создаем таблицу для анонимных сообщений
def create_anonymous_messages_table(cursor):
    cursor.execute('''CREATE TABLE IF NOT EXISTS anonymous_messages
                      (sender_id INTEGER, recipient_id INTEGER, message TEXT)''')

# Функция для записи сообщения пользователя в лог
def log_user_message(user_id, message_text):
    logging.info(f"Пользователь {user_id} отправил сообщение: {message_text}")

# Функция для отправки сообщения получателю с указанием форматирования
def send_message_to_recipient(recipient_id, message, reply_markup=None, parse_mode=None):
    bot.send_message(recipient_id, message, reply_markup=reply_markup, parse_mode=parse_mode)

# Обработчик для команды /start
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    user_username = message.from_user.username

    # Логируем команду /start
    logging.info(f"Пользователь {user_id} ({user_username}) ввел команду /start")

    if len(message.text.split()) > 1:
        recipient_id = int(message.text.split()[1])

        # Подключаемся к базе данных
        conn, cursor = connect_to_database()

        # Создаем таблицы, если их нет
        create_users_table(cursor)
        create_anonymous_messages_table(cursor)

        # Сохраняем информацию о пользователе в базе данных
        cursor.execute("INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)", (user_id, user_username))
        conn.commit()

        # Логируем создание записи о пользователе
        logging.info(f"Создана запись о пользователе {user_id} ({user_username})")

        # Отправляем сообщение для отправки вам анонимных вопросов
        if user_id == recipient_id:
            bot.send_message(user_id, "<b>Напиши мне анонимный вопрос:</b>\n<i>(ты нажал на свою ссылку)</i>", parse_mode="HTML")
        else:
            bot.send_message(user_id, "<b>Напиши мне анонимный вопрос:</b>\n<i>(и тоже сможешь получать вопросы)</i>", parse_mode="HTML")
            
        # Закрываем соединение с базой данных
        conn.close()

        bot.register_next_step_handler(message, receive_message, recipient_id=recipient_id)
    else:
        # Отправляем ссылку для отправки анонимных вопросов
        bot.send_message(user_id, f"<b>Твоя ссылка для вопросов:</b>\n"
                          f"<a href='t.me/{bot.get_me().username}?start={user_id}'>t.me/{bot.get_me().username}?start={user_id}</a>\n\n"
                          "Покажи эту ссылку друзьям и подписчикам и получай от них анонимные вопросы!",
                          parse_mode="HTML")

        # Логируем отправку ссылки
        logging.info(f"Пользователь {user_id} ({user_username}) получил ссылку для вопросов")

# Обработчик для анонимных сообщений
def receive_message(message, recipient_id):
    user_id = message.from_user.id
    user_message = message.text
    
    # Записываем сообщение пользователя в лог
    log_user_message(user_id, user_message)
    
    # Подключаемся к базе данных
    conn, cursor = connect_to_database()
    
    # Проверяем, есть ли адресат сообщения в базе данных
    cursor.execute("SELECT id FROM users WHERE id = ?", (recipient_id,))
    recipient_exists = cursor.fetchone()
    
    if recipient_exists:
        # Сохраняем анонимное сообщение и адресата в базе данных
        cursor.execute("INSERT INTO anonymous_messages (sender_id, recipient_id, message) VALUES (?, ?, ?)",
                       (user_id, recipient_id, user_message))
        conn.commit()
        # Отправляем подтверждение
        bot.send_message(user_id, "✅ Ваш вопрос анонимно отправлен, ожидайте ответ!")

        # Отправляем сообщение получателю с кнопкой "Ответить"
        send_message_to_recipient(recipient_id, f"<b>У вас новый анонимный вопрос:</b>\n\n<i>{user_message}</i>", reply_markup=create_reply_button(user_id), parse_mode="HTML")
    else:
        bot.send_message(user_id, "Извините, адресат не найден.")
    
    # Закрываем соединение с базой данных
    conn.close()

# Функция для обработки анонимного ответа пользователя
def handle_reply(message, sender_id, recipient_id):
    user_message = message.text

    # Логируем анонимный ответ
    logging.info(f"Пользователь {sender_id} отправил анонимный ответ для пользователя {recipient_id}")

    # Отправляем анонимный ответ получателю
    send_message_to_recipient(recipient_id, f"<b>У тебя новый анонимный ответ:</b>\n\n<i>{user_message}</i>",reply_markup=create_reply_button(sender_id),parse_mode="HTML")

    # Отправляем подтверждение отправителю
    response_message = "✅ Ответ отправлен!\n\n"
    response_message += "Твоя ссылкa для вопросов:\n"
    response_message += f"t.me/{bot.get_me().username}?start={sender_id}\n\n"
    response_message += "Покажи эту ссылку друзьям и подписчикам и получай от них анонимные вопросы!"

    # Отправляем анонимный ответ отправителю 
    bot.send_message(sender_id, response_message, parse_mode="HTML")

    # Опционально, сохраняем анонимный ответ в базе данных
    conn, cursor = connect_to_database()

    cursor.execute("INSERT INTO anonymous_messages (sender_id, recipient_id, message) VALUES (?, ?, ?)",
                   (sender_id, recipient_id, user_message))
    conn.commit()

    conn.close()
    
# Создаем кнопку "Ответить" для получателя
def create_reply_button(user_id):
    markup = types.InlineKeyboardMarkup()
    reply_button = types.InlineKeyboardButton("✏ Ответить", callback_data=f"reply_{user_id}")
    markup.add(reply_button)
    return markup
    
# Обработчик для кнопки "Ответить"
@bot.callback_query_handler(func=lambda call: call.data.startswith('reply_'))
def reply_to_sender(call):
    sender_id = call.from_user.id
    recipient_id = call.data.split('_')[1]

    # Логируем нажатие кнопки "Ответить"
    logging.info(f"Пользователь {sender_id} нажал кнопку 'Ответить' для пользователя {recipient_id}")

    # Отправляем сообщение "Напиши анонимный ответ:"
    bot.send_message(sender_id, "<b>Напиши анонимный ответ:</b>", parse_mode="HTML")

    # Создаем состояние ожидания ответа от пользователя
    bot.register_next_step_handler(call.message, handle_reply, sender_id, recipient_id)

# Остальной код...

if __name__ == '__main__':
        bot.polling(none_stop=True)
       