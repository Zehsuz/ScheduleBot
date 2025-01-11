#  ZZZZZZ  AAAAA  H   H   AAAAA  RRRRRR   I TTTTT   AAAAA
#    Z    A     A H   H  A     A R     R      T    A     A
#   Z     AAAAAAA HHHHH  AAAAAAA RRRRRR   I   T    AAAAAAA
#  Z      A     A H   H  A     A R   R    I   T    A     A
# ZZZZZZ  A     A H   H  A     A R    R   I   T    A     A

import os
import sqlite3
import sys
from threading import Thread
from time import sleep
import telebot
from telebot import types
import time
import threading
import logging
import datetime
# import traceback

# Константы и настройки
TOKEN = 'YOUR_BOT_TOKEN'
DATABASE = 'users.db'
BUTTONS = {
    'today':types.KeyboardButton(text='Расписание на сегодня'),
    'next_day': types.KeyboardButton(text='Расписание на завтра'),
    'all_users_notf': types.KeyboardButton(text='Уведомление всем пользователям'),
    'redact': types.KeyboardButton(text='параметры администратора'),
    'back': types.KeyboardButton(text='назад'),
    'commands': types.KeyboardButton(text='команды'),
    'notf_on': types.KeyboardButton(text='включить уведомления'),
    'notf_off': types.KeyboardButton(text='Выключить уведомления'),
    'settings_notf': types.KeyboardButton(text='центр уведомлений'),
    'admins_notf': types.KeyboardButton(text='уведомление администраторам'),
    'redact_tomorrow': types.KeyboardButton(text='Редактировать расписание на завтра'),
    'cancel_replacement': types.KeyboardButton(text='Отменить замену на завтра'),
    'edit_replacement': types.KeyboardButton(text='Изменить замену на завтра'),
    'create_replacement': types.KeyboardButton(text='Создать замену'),
    'admins': types.KeyboardButton(text='администраторы'),
    'childe': types.KeyboardButton(text='все пользователи'),
    'edit_db': types.KeyboardButton(text='Редактировать базу данных'),
    'edit_admin_level': types.KeyboardButton(text='Изменить уровень администратора'),
    'edit_user_name': types.KeyboardButton(text='Изменить имя пользователя')
}
schedule = ''
CHAT_ID = "ADMIN_CHAT_ID"  # Ваш Telegram ID или чат ID

# Настройка логирования
logging.basicConfig(level=logging.INFO)


# Функция для отправки уведомлений о сбоях
def send_error_notification(error_message):
    try:
        bot.send_message(CHAT_ID, f"Бот упал с ошибкой: {error_message}")
    except Exception as e:
        logging.error(f"Не удалось отправить уведомление о сбое: {e}")
        # bot.send_message(CHAT_ID, f"Бот упал с ошибкой? проверьте консоль")


def restart_bot():
    # Перезапуск бота.
    logging.error("Произошла ошибка. Перезапуск бота.")
    os.execv(sys.executable, ['python'] + sys.argv)  # Перезапуск скрипта


# Настройка бота
bot = telebot.TeleBot(TOKEN)


# Вспомогательные функции
def get_week_type(current_week):
    # Определяет тип недели (четная или нечетная).
    academic_week_number = current_week - 47  # Смещение от 48-й недели
    return "четная" if academic_week_number % 2 == 0 else "нечетная"


def schedule_today():
    # Возвращает день недели на сегодня на русском языке.
    today = datetime.datetime.now()
    day_of_week = today.strftime("%A")
    days_mapping = {
        "Monday": "Понедельник",
        "Tuesday": "Вторник",
        "Wednesday": "Среда",
        "Thursday": "Четверг",
        "Friday": "Пятница",
        "Saturday": "Суббота",
        "Sunday": "Воскресенье"
    }
    return days_mapping.get(day_of_week, "Неизвестный день")


def schedule_tomorrow():
    # Возвращает день недели на завтра на русском языке.
    tomorrow = datetime.datetime.now() + datetime.timedelta(days=1)
    day_of_week = tomorrow.strftime("%A")
    days_mapping = {
        "Monday": "Понедельник",
        "Tuesday": "Вторник",
        "Wednesday": "Среда",
        "Thursday": "Четверг",
        "Friday": "Пятница",
        "Saturday": "Суббота",
        "Sunday": "Воскресенье"
    }
    return days_mapping.get(day_of_week, "Неизвестный день")


@bot.message_handler(func=lambda message: message.text.lower() == 'параметры администратора')
def update_schedule_replacement(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_data = get_user_data(user_id)
    admin_level = user_data['admin_level']

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    if admin_level == 3:
        kb.add(BUTTONS['redact_tomorrow'], BUTTONS['settings_notf'])
        kb.add(BUTTONS['back'])
    elif admin_level == 2:
        kb.add(BUTTONS['redact_tomorrow'], BUTTONS['admins_notf'])
        kb.add(BUTTONS['back'])
    elif admin_level == 4:
        kb.add(BUTTONS['redact_tomorrow'], BUTTONS['settings_notf'])
        kb.add(BUTTONS['edit_db'], BUTTONS['back'])


    bot.send_message(chat_id, "Выберете опцию:", reply_markup=kb)


def load_schedule_for_day(day_type):
    global schedule
    today = datetime.date.today()

    # Определяем текущий день и неделю для запроса
    current_week = today.isocalendar()[1] if day_type == 'today' else \
        (today + datetime.timedelta(days=1)).isocalendar()[1]
    week_type = get_week_type(current_week)
    day_name = schedule_today() if day_type == 'today' else schedule_tomorrow()

    # Проверяем, есть ли замена для этого дня
    if check_replacement(day_name, week_type):
        schedule = f"Есть замена на {day_name} ({week_type})"
    else:
        try:
            if day_name != 'Воскресенье':
                with open(f'days/{day_name}_{week_type}.txt',
                          'r',
                          encoding='utf-8') as file:
                    schedule = file.read()
            else:
                schedule = f"{'Сегодня' if day_type == 'today' else 'Завтра'} воскресенье, спи спокойно"
        except FileNotFoundError:
            schedule = "Расписание не найдено."


# Работа с базой данных
def get_connection():
    # Создает подключение к базе данных и возвращает его.
    conn = sqlite3.connect(DATABASE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(
        "PRAGMA journal_mode = WAL;")  # Включаем режим Write-Ahead Logging
    return conn, cursor


def close_connection(conn, cursor):
    # Закрывает соединение с базой данных.
    cursor.close()
    conn.close()


def get_user_data(user_id):
    # Получает данные пользователя по его ID.
    conn, cursor = get_connection()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id, ))
    user = cursor.fetchone()
    close_connection(conn, cursor)
    if user:
        return {
            "user_id": user[0],
            "chat_id": user[1],
            "admin_level": user[2],
            "notifications": user[3]
        }
    return None


def register_user(user_id, chat_id):
    # Регистрирует нового пользователя в базе данных.
    conn, cursor = get_connection()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id, ))
    user = cursor.fetchone()
    if user:
        close_connection(conn, cursor)
        return False  # Пользователь уже зарегистрирован
    else:
        cursor.execute("INSERT INTO users (user_id, chat_id) VALUES (?, ?)",
                       (user_id, chat_id))
        conn.commit()
        close_connection(conn, cursor)
        return True


# Основная логика бота
def setup_database():
    # Настройка базы данных и создание таблиц пользователей и замены, если они не существуют.
    conn, cursor = get_connection()

    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        chat_id INTEGER NOT NULL,
        admin_level INTEGER DEFAULT 0,
        notifications INTEGER DEFAULT 0
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS replacements (
        day TEXT NOT NULL,
        week_type TEXT NOT NULL,
        has_replacement INTEGER DEFAULT 0,
        PRIMARY KEY (day, week_type)
    )''')

    conn.commit()
    close_connection(conn, cursor)


@bot.message_handler(commands=['help', 'start'])
def send_welcome(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if register_user(user_id, chat_id):
        bot.reply_to(message, "Вы успешно зарегистрированы!")
    else:
        bot.reply_to(message, "Вы уже зарегистрированы!")

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(BUTTONS['today'], BUTTONS['commands'])
    bot.send_message(chat_id, 'Выберите опцию:', reply_markup=kb)


# Исправленный обработчик для команды "кто я" и кнопки "команды"
@bot.message_handler(func=lambda message: message.text.lower() == 'кто я' or message.text.lower() == 'команды' or message.text.lower() == 'назад')
def admin_panel(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_data = get_user_data(user_id)
    if user_data:
        admin_level = user_data["admin_level"]
        user_notifications = user_data['notifications']
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        if admin_level == 0:
            if user_notifications == 0:
                kb.add(BUTTONS['today'], BUTTONS['next_day'],
                       BUTTONS['notf_on'])
            elif user_notifications == 1:
                kb.add(BUTTONS['today'], BUTTONS['next_day'],
                       BUTTONS['notf_off'])
            bot.send_message(chat_id,
                             "все на что ты способен",
                             reply_markup=kb)
        elif admin_level == 1:
            if user_notifications == 0:
                kb.add(BUTTONS['today'], BUTTONS['next_day'],
                       BUTTONS['notf_on'], BUTTONS['all_users_notf'])
            elif user_notifications == 1:
                kb.add(BUTTONS['today'], BUTTONS['next_day'],
                       BUTTONS['notf_off'], BUTTONS['all_users_notf'])
            bot.send_message(chat_id,
                             "Комфорт челикс сила 1.",
                             reply_markup=kb)
        elif admin_level == 2:
            if user_notifications == 0:
                kb.add(BUTTONS['today'], BUTTONS['next_day'],
                       BUTTONS['redact'], BUTTONS['notf_on'])
            elif user_notifications == 1:
                kb.add(BUTTONS['today'], BUTTONS['next_day'],
                       BUTTONS['redact'], BUTTONS['notf_off'])
            bot.send_message(chat_id, "Зам старосты сила 2.", reply_markup=kb)
        elif admin_level == 3:
            if user_notifications == 0:
                kb.add(BUTTONS['today'], BUTTONS['next_day'],
                       BUTTONS['redact'], BUTTONS['notf_on'])
            elif user_notifications == 1:
                kb.add(BUTTONS['today'], BUTTONS['next_day'],
                       BUTTONS['redact'], BUTTONS['notf_off'])
            bot.send_message(chat_id, "Староста, сила 3.", reply_markup=kb)
        elif admin_level == 4:
            if user_notifications == 0:
                kb.add(BUTTONS['today'], BUTTONS['next_day'],
                       BUTTONS['notf_on'], BUTTONS['redact'],
                       BUTTONS['admins'], BUTTONS['childe'])
            elif user_notifications == 1:
                kb.add(BUTTONS['today'], BUTTONS['next_day'],
                       BUTTONS['notf_off'], BUTTONS['redact'],
                       BUTTONS['admins'], BUTTONS['childe'])
            bot.send_message(chat_id, "Отец.", reply_markup=kb)
        else:
            bot.reply_to(message, "Неизвестный уровень администратора.")
    else:
        bot.reply_to(message, "Вы не зарегистрированы в системе.")


@bot.message_handler(func=lambda message: message.text.lower() == 'все пользователи')
def childes(message):
    global notf_users
    conn, cursor = get_connection()
    cursor.execute("SELECT * FROM users")
    lst_all_admins = cursor.fetchall()

    # Формируем строку с информацией о каждом пользователе
    users_info = ""
    for user in lst_all_admins:
        user_id = user[0]
        chat_id = user[1]
        admin_level = user[2]
        notifications = user[3]
        user_name = user[4] if user[
            4] else "Имя пользователя отсутствует"  # Проверка имени пользователя
        waiting_for_replacement = user[5]

        # Формируем строку для каждого пользователя
        users_info += f"user_id: {user_id}, chat_id: {chat_id}, admin_level: {admin_level}, notifications: {notifications}, user_name: {user_name}, waiting_for_replacement: {waiting_for_replacement} \n\n"
        with open('users.txt', 'w', encoding='utf-8') as file:
            file.write(users_info)
    # Отправляем сообщение создателю бота
    bot.send_message(1330649108, users_info)


@bot.message_handler(
    func=lambda message: message.text.lower() == 'администраторы')
def fathers(message):
    global notf_users
    conn, cursor = get_connection()
    cursor.execute("SELECT * FROM users WHERE admin IN (?, ?, ?, ?)",
                   (1, 2, 3, 4))
    lst_all_admins = cursor.fetchall()

    # Формируем строку с информацией о администраторах

    admin_info = ""
    for user in lst_all_admins:
        user_id = user[0]
        chat_id = user[1]
        admin_level = user[2]
        notifications = user[3]
        user_name = user[4] if user[
            4] else "Имя пользователя отсутствует"  # Проверка имени пользователя
        waiting_for_replacement = user[5]

        # Формируем строку для каждого администратора

        admin_info += f"user_id: {user_id}, chat_id: {chat_id}, admin_level: {admin_level}, notifications: {notifications}, user_name: {user_name}, waiting_for_replacement: {waiting_for_replacement} \n\n"
    with open('admins.txt', 'w', encoding='utf-8') as file:
        file.write(admin_info)
    # Отправляем сообщение создателю бота
    bot.send_message(1330649108, admin_info)


@bot.message_handler(
    func=lambda message: message.text.lower() == 'редактировать базу данных')
def edit_database(message):
    # Отправляем пользователю выбор действия
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(BUTTONS['edit_admin_level'], BUTTONS['edit_user_name'])
    kb.add(BUTTONS['back'])
    msg = bot.send_message(message.chat.id,"Что вы хотите изменить?", reply_markup=kb)
    bot.register_next_step_handler(msg, process_db_action)


# Обработка выбора действия для редактирования
def process_db_action(message):
    if message.text == 'Изменить уровень администратора':
        msg = bot.send_message(message.chat.id,"Введите user_id пользователя, чей уровень администрирования хотите изменить:")
        bot.register_next_step_handler(msg, process_user_id_for_admin_level)
    elif message.text == 'Изменить имя пользователя':
        msg = bot.send_message(
            message.chat.id,
            "Введите user_id пользователя, чье имя хотите изменить:")
        bot.register_next_step_handler(msg, process_user_id_for_user_name)
    elif message.text == 'назад':
        # Возврат в главное меню
        bot.send_message(message.chat.id,"Возвращаюсь в главное меню...", reply_markup=types.ReplyKeyboardRemove())
        admin_panel(message)


# Обработка user_id для изменения уровня администрирования
def process_user_id_for_admin_level(message):
    user_id = message.text
    conn, cursor = get_connection()

    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id, ))
    user = cursor.fetchone()

    if user:
        user_id = user[0]
        chat_id = user[1]
        admin_level = user[2]
        notifications = user[3]
        user_name = user[4] if user[4] else "Имя пользователя отсутствует"
        waiting_for_replacement = user[5]

        user_info = f"user_id: {user_id}, chat_id: {chat_id}, admin_level: {admin_level}, notifications: {notifications}, user_name: {user_name}, waiting_for_replacement: {waiting_for_replacement}"
        bot.send_message(message.chat.id,f"Информация о пользователе:\n{user_info}")

        msg = bot.send_message(message.chat.id,"Введите новый уровень администрирования для этого пользователя:")
        bot.register_next_step_handler(msg, process_new_admin_level, user_id, conn)
    else:
        bot.send_message(message.chat.id,"Пользователь не найден в базе данных.")
        conn.close()


# Обработка изменения уровня администрирования
def process_new_admin_level(message, user_id, conn):
    try:
        new_admin_level = int(message.text)

        cursor = conn.cursor()
        cursor.execute("UPDATE users SET admin=? WHERE user_id=?", (new_admin_level, user_id))
        conn.commit()

        bot.send_message(message.chat.id,f"Уровень администрирования для пользователя {user_id} изменен на {new_admin_level}.")
    except ValueError:
        bot.send_message(message.chat.id,"Пожалуйста, введите целое число для уровня администрирования.")

    conn.close()


# Обработка user_id для изменения имени пользователя
def process_user_id_for_user_name(message):
    user_id = message.text
    conn, cursor = get_connection()

    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id, ))
    user = cursor.fetchone()

    if user:
        user_id = user[0]
        chat_id = user[1]
        admin_level = user[2]
        notifications = user[3]
        user_name = user[4] if user[4] else "Имя пользователя отсутствует"
        waiting_for_replacement = user[5]

        user_info = f"user_id: {user_id}, chat_id: {chat_id}, admin_level: {admin_level}, notifications: {notifications}, user_name: {user_name}, waiting_for_replacement: {waiting_for_replacement}"
        bot.send_message(message.chat.id,f"Информация о пользователе:\n{user_info}")

        msg = bot.send_message(message.chat.id, "Введите новое имя пользователя для этого пользователя:")
        bot.register_next_step_handler(msg, process_new_user_name, user_id,conn)
    else:
        bot.send_message(message.chat.id,"Пользователь не найден в базе данных.")
        conn.close()


# Обработка изменения имени пользователя
def process_new_user_name(message, user_id, conn):
    new_user_name = message.text

    cursor = conn.cursor()
    cursor.execute("UPDATE users SET user_name=? WHERE user_id=?", (new_user_name, user_id))
    conn.commit()

    bot.send_message(message.chat.id,f"Имя пользователя для пользователя {user_id} изменено на {new_user_name}.")
    conn.close()


# Для команды настройки уведомлений
@bot.message_handler(func=lambda message: message.text.lower() == 'центр уведомлений')
def settings_notofocations(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_data = get_user_data(user_id)
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    admin_level = user_data["admin_level"]
    if admin_level == 2:
        kb.add(BUTTONS['all_users_notf'], BUTTONS['admins_notf'])
        kb.add(BUTTONS['back'])
    elif admin_level == 3:
        kb.add(BUTTONS['all_users_notf'], BUTTONS['admins_notf'])
        kb.add(BUTTONS['back'])
    elif admin_level == 4:
        kb.add(BUTTONS['all_users_notf'], BUTTONS['admins_notf'])
        kb.add(BUTTONS['back'])
    bot.send_message(chat_id,"Выберите кому отправить уведомление:", reply_markup=kb)


@bot.message_handler(func=lambda message: message.text.lower() == 'редактировать расписание на завтра')
def redact_tomorrow(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_data = get_user_data(user_id)
    admin_level = user_data['admin_level']

    if admin_level >= 2:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        kb.add(BUTTONS['create_replacement'], BUTTONS['edit_replacement'],
               BUTTONS['cancel_replacement'])
        kb.add(BUTTONS['back'])
        bot.send_message(chat_id,"Выберите действие с заменой на завтра:", reply_markup=kb)


def create_replacement():
    # Проверяем, существует ли уже файл с заменами на завтра
    if not os.path.exists('replacement_tomorrow.txt'):
        # Создаем файл и записываем, что замен нет
        with open('replacement_tomorrow.txt', 'w', encoding='utf-8') as file:
            file.write("Замен на завтра нет.")
    return "Файл с заменами на завтра был создан или уже существует."


def save_user_data(user_id, user_data):
    # Здесь сохраняем состояние пользователя, например, в базу данных
    conn, cursor = get_connection()
    cursor.execute(
        "UPDATE users SET waiting_for_replacement = ? WHERE user_id = ?",(user_data['waiting_for_replacement'], user_id))
    conn.commit()
    close_connection(conn, cursor)


@bot.message_handler(func=lambda message: message.text.lower() == 'создать замену')
def handle_create_replacement(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    # Проверяем, имеет ли пользователь права администратора
    user_data = get_user_data(user_id)
    if user_data and user_data['admin_level'] >= 2:
        # Создаем файл для замены, если его нет
        creation_message = create_replacement()
        bot.send_message(chat_id, creation_message)

        # Запрашиваем у администратора информацию о замене
        # bot.send_message(chat_id, "Теперь напишите, какая замена будет на завтра (например, 'Замена по математике: 10:00').")
        edit_replacement(message)
        # Сохраняем состояние, чтобы знать, что ожидаем ввод замены
        # Сохраняем в памяти, что ожидаем замены от этого пользователя
        user_data['waiting_for_replacement'] = True
        save_user_data(user_id, user_data)
    # else:
    #     bot.send_message(chat_id,"У вас нет прав для выполнения этой команды.")


@bot.message_handler(func=lambda message: message.text and 'замена' in message.text.lower())
def handle_replacement_details(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    # Получаем данные пользователя
    user_data = get_user_data(user_id)
    if user_data and user_data.get('waiting_for_replacement', False):
        # Получаем текст замены от администратора
        replacement_text = message.text.strip()

        # Записываем замены в файл
        with open('replacement_tomorrow.txt', 'w', encoding='utf-8') as file:
            file.write(replacement_text)

        # Убираем флаг ожидания
        user_data['waiting_for_replacement'] = False
        save_user_data(user_id, user_data)

        # Подтверждаем создание замены
        bot.send_message(
            chat_id, f"Замена на завтра была добавлена: {replacement_text}")
    else:
        handle_create_replacement(message)


@bot.message_handler(func=lambda message: message.text.lower() == 'изменить замену на завтра')
def edit_replacement(message):
    load_schedule_for_day('tomorrow')
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_data = get_user_data(user_id)
    admin_level = user_data['admin_level']

    if admin_level >= 2:
        bot.send_message(
            chat_id, "Введите новый текст замены для расписания на завтра.")
        bot.register_next_step_handler(message, process_new_replacement)
    # else:
    #     bot.send_message(chat_id, "У вас недостаточно прав для редактирования расписания.")


def create_replacement_file():
    # Проверяем, существует ли уже файл с заменами на завтра
    if not os.path.exists('replacement_tomorrow.txt'):
        with open('replacement_tomorrow.txt', 'w', encoding='utf-8') as file:
            file.write("Замен на завтра нет.")  # Если файла нет, записываем что замен нет

    # Возвращаем сообщение о создании или отсутствии файла
    return "Файл с заменами на завтра был создан или уже существует."


def process_new_replacement(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    new_replacement_text = message.text
    # Сохраняем новую замену в файл
    with open('replacement_tomorrow.txt', 'w', encoding='utf-8') as file:
        file.write(new_replacement_text)
    global notf_users
    conn, cursor = get_connection()
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    with open('replacement_tomorrow.txt', 'r', encoding='utf-8') as file:
        notf_users = file.read()
    for user in users:
        user_data = {
            'user_id': user[0],
            'chat_id': user[1],
            'admin_level': user[2],
            'notifications': user[3]
        }
        try:
            if not notf_users:
                notf_users = schedule
            # Попытка отправить сообщение
            bot.send_message(user_data['user_id'], f'{notf_users}')

        except telebot.apihelper.ApiTelegramException as e:
            # Логируем ошибку, если chat_id не найден
            logging.error(f"Не удалось отправить сообщение пользователю {user_data['user_id']}: {e}")

        except Exception as e:
            # Общая ошибка
            logging.error(f"Ошибка при отправке сообщения: {e}")

    bot.send_message(message.chat.id,'Уведомление отправлено всем пользователям.')
    bot.send_message(chat_id, "Замена на завтра успешно обновлена.")


@bot.message_handler(
    func=lambda message: message.text.lower() == 'отменить замену на завтра')
def cancel_replacement(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_data = get_user_data(user_id)
    admin_level = user_data['admin_level']

    if admin_level >= 2:
        # Удаляем файл с заменой, тем самым отменяя замену
        if os.path.exists('replacement_tomorrow.txt'):
            os.remove('replacement_tomorrow.txt')
            bot.send_message(chat_id, "Замена на завтра успешно отменена.")
            conn, cursor = get_connection()
            cursor.execute(
                "INSERT OR REPLACE INTO replacements (day, week_type, has_replacement) VALUES (?, ?, ?)",
                ("Сегодня", get_week_type(datetime.date.today().isocalendar()[1]), 0))
            conn.commit()
            close_connection(conn, cursor)
        else:
            bot.send_message(chat_id, "Замена на завтра не была установлена.")


def load_schedule_for_day(day_type):
    global schedule
    today = datetime.date.today()
    current_week = today.isocalendar()[1] if day_type == 'today' else \
    (today + datetime.timedelta(days=1)).isocalendar()[1]
    week_type = get_week_type(current_week)
    day_name = schedule_today() if day_type == 'today' else schedule_tomorrow()

    # Проверка на замену
    replacement_file = 'replacement_tomorrow.txt'
    if day_type == 'tomorrow' and os.path.exists(replacement_file):
        with open(replacement_file, 'r', encoding='utf-8') as file:
            schedule = file.read()
    else:
        try:
            if day_name != 'Воскресенье':
                with open(f'days/{day_name}_{week_type}.txt', 'r', encoding='utf-8') as file:
                    schedule = file.read()
            else:
                schedule = 'Сегодня воскресенье, спи спокойно'
        except FileNotFoundError:
            schedule = "Расписание не найдено."


@bot.message_handler(
    func=lambda message: message.text.lower() == 'снять замену сегодня')
def remove_replacement_today(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_data = get_user_data(user_id)
    admin_level = user_data['admin_level']

    if admin_level >= 3:
        conn, cursor = get_connection()
        cursor.execute(
            "INSERT OR REPLACE INTO replacements (day, week_type, has_replacement) VALUES (?, ?, ?)",
            ("Сегодня", get_week_type(datetime.date.today().isocalendar()[1]), 0))

        conn.commit()
        close_connection(conn, cursor)

        global notf_users
        conn, cursor = get_connection()
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        for user in users:
            user_data = {
                'user_id': user[0],
                'chat_id': user[1],
                'admin_level': user[2],
                'notifications': user[3]
            }
            try:
                # Попытка отправить сообщение
                bot.send_message(
                    user_data['user_id'],
                    f' замена была снята, расписание на завтра: \n {schedule}')
            except telebot.apihelper.ApiTelegramException as e:
                # Логируем ошибку, если chat_id не найден
                logging.error(f"Не удалось отправить сообщение пользователю {user_data['user_id']}: {e}")
            except Exception as e:
                # Общая ошибка
                logging.error(f"Ошибка при отправке сообщения: {e}")

        bot.send_message(chat_id, "Замена на сегодня снята.")
    else:
        bot.send_message(chat_id,"У вас недостаточно прав для изменения расписания.")


@bot.message_handler(func=lambda message: message.text.lower() == 'снять замену завтра')
def remove_replacement_tomorrow(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_data = get_user_data(user_id)
    admin_level = user_data['admin_level']

    if admin_level >= 2:
        conn, cursor = get_connection()
        cursor.execute(
            "INSERT OR REPLACE INTO replacements (day, week_type, has_replacement) VALUES (?, ?, ?)",
            ("Завтра",get_week_type((datetime.date.today() + datetime.timedelta(days=1)).isocalendar()[1]), 0))
        conn.commit()
        close_connection(conn, cursor)
        bot.send_message(chat_id, "Замена на завтра снята.")
    else:
        bot.send_message(chat_id,"У вас недостаточно прав для изменения расписания.")


def check_replacement(day, week_type):
    conn, cursor = get_connection()
    cursor.execute("SELECT has_replacement FROM replacements WHERE day = ? AND week_type = ?",(day, week_type))
    result = cursor.fetchone()
    close_connection(conn, cursor)

    if result:
        return result[0] == 1
    return False


@bot.message_handler(func=lambda message: message.text.lower() == 'уведомление всем пользователям')
def all_users_notf(message):
    bot.send_message(message.chat.id,'Напишите сообщение которое отправитсья всем пользователям:')

    bot.register_next_step_handler(message, save_notification_text)


def send_notification_to_all_users(message):
    global notf_users
    conn, cursor = get_connection()
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()

    for user in users:
        user_data = {
            'user_id': user[0],
            'chat_id': user[1],
            'admin_level': user[2],
            'notifications': user[3]
        }
        try:
            # Попытка отправить сообщение
            bot.send_message(user_data['user_id'], f'{notf_users}')
        except telebot.apihelper.ApiTelegramException as e:
            # Логируем ошибку, если chat_id не найден
            logging.error(f"Не удалось отправить сообщение пользователю {user_data['user_id']}: {e}")
        except Exception as e:
            # Общая ошибка
            logging.error(f"Ошибка при отправке сообщения: {e}")

    bot.send_message(message.chat.id,'Уведомление отправлено всем пользователям.')


def save_notification_text(message):
    global notf_users
    notf_users = message.text  # Сохраняем текст уведомления в переменную

    # После этого отправляем уведомление всем пользователям
    send_notification_to_all_users(message)


@bot.message_handler(func=lambda message: message.text.lower() == 'уведомление администраторам')
def all_users_notf(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    admin_level = user_data["admin_level"]
    if admin_level == 2 or admin_level == 3 or admin_level == 4:
        bot.send_message(message.chat.id,'Напишите сообщение которое отправитсья всем администраторам:')
        bot.register_next_step_handler(message, save_notification_text_admin)


def save_notification_text_admin(message):
    global notf_users
    notf_users = message.text  # Сохраняем текст уведомления в переменную

    # После этого отправляем уведомление всем пользователям
    send_notification_to_admin(message)


def send_notification_to_admin(message):
    global notf_users
    conn, cursor = get_connection()
    cursor.execute("SELECT * FROM users WHERE admin IN (?, ?, ?, ?)",(1, 2, 3, 4))
    users = cursor.fetchall()

    # Перебираем всех пользователей и отправляем уведомление
    for user in users:
        user_data = {
            'user_id': user[0],
            'chat_id': user[1],
            'admin_level': user[2],
            'notofications': user[3]
        }

        # Отправляем текст уведомления всем пользователям
        try:
            bot.send_message(user_data['user_id'], f'{notf_users}')
        except telebot.apihelper.ApiTelegramException as e:
            # Логируем ошибку, если chat_id не найден
            logging.error(f"Не удалось отправить сообщение пользователю {user_data['user_id']}: {e}")
        except Exception as e:
            # Общая ошибка
            logging.error(f"Ошибка при отправке сообщения: {e}")

    # Информируем администратора о том, что уведомление отправлено
    bot.send_message(message.chat.id,'Уведомление отправлено всем администраторам.')


@bot.message_handler(func=lambda message: message.text.lower() == 'выключить уведомления')
def notf_off(message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_data = get_user_data(user_id)
    user_notifications = user_data['notifications']
    admin_level = user_data['admin_level']
    if user_notifications == 0:
        if admin_level == 0:
            kb.add(BUTTONS['today'], BUTTONS['next_day'], BUTTONS['notf_on'])
        elif admin_level == 4:
            kb.add(BUTTONS['today'], BUTTONS['next_day'], BUTTONS['redact'], BUTTONS['notf_on'], BUTTONS['admins'], BUTTONS['childe'])
        elif admin_level >= 1:
            kb.add(BUTTONS['today'], BUTTONS['next_day'], BUTTONS['redact'], BUTTONS['notf_on'])
        bot.send_message(chat_id,"Уведомления и так выключены", reply_markup=kb)
        # bot.send_message(chat_id,  "Уведомления и так выключены", reply_markup=kb)
    else:
        conn, cursor = get_connection()
        cursor.execute("UPDATE users SET notifications = 0 WHERE user_id = ?",(user_id, ))
        if admin_level == 0:
            kb.add(BUTTONS['today'], BUTTONS['next_day'], BUTTONS['notf_on'])
        elif admin_level == 4:
            kb.add(BUTTONS['today'], BUTTONS['next_day'], BUTTONS['redact'], BUTTONS['notf_on'], BUTTONS['admins'], BUTTONS['childe'])
        elif admin_level >= 1:
            kb.add(BUTTONS['today'], BUTTONS['next_day'], BUTTONS['redact'], BUTTONS['notf_on'])
        bot.send_message(chat_id, "Уведомления выключены", reply_markup=kb)
        conn.commit()
        close_connection(conn, cursor)


@bot.message_handler(func=lambda message: message.text.lower() == 'включить уведомления')
def notf_on(message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_data = get_user_data(user_id)
    user_notifications = user_data['notifications']
    admin_level = user_data['admin_level']
    if user_notifications == 1:
        if admin_level == 0:
            kb.add(BUTTONS['today'], BUTTONS['next_day'], BUTTONS['notf_off'])
        elif admin_level == 4:
            kb.add(BUTTONS['today'], BUTTONS['next_day'], BUTTONS['redact'], BUTTONS['notf_off'], BUTTONS['admins'], BUTTONS['childe'])
            bot.send_message(chat_id, "Уведомления и так выключены", reply_markup=kb)
        elif admin_level >= 1:
            kb.add(BUTTONS['today'], BUTTONS['next_day'], BUTTONS['redact'], BUTTONS['notf_off'])
        bot.send_message(chat_id,"Уведомления и так включены", reply_markup=kb)
    else:
        conn, cursor = get_connection()
        cursor.execute("UPDATE users SET notifications = 1 WHERE user_id = ?",(user_id, ))
        if admin_level == 0:
            kb.add(BUTTONS['today'], BUTTONS['next_day'], BUTTONS['notf_off'])
        elif admin_level == 4:
            kb.add(BUTTONS['today'], BUTTONS['next_day'], BUTTONS['redact'], BUTTONS['notf_off'], BUTTONS['admins'], BUTTONS['childe'])
        elif admin_level >= 1:
            kb.add(BUTTONS['today'], BUTTONS['next_day'], BUTTONS['redact'], BUTTONS['notf_off'])
        bot.send_message(chat_id, "Уведомления включены", reply_markup=kb)
        conn.commit()
        close_connection(conn, cursor)


# Для команды расписания на сегодня
@bot.message_handler(func=lambda message: message.text.lower() == 'расписание на сегодня')
def today_schedule(message):
    load_schedule_for_day('today')
    chat_id = message.chat.id
    if schedule_today() == "Воскресенье":
        bot.send_message(chat_id, "Сегодня воскресенье. Расписания нет.")
    else:
        bot.send_message(chat_id, f"Сегодня {schedule}")
        print(f'расписание отправлено пользователю {chat_id}, в {datetime.datetime.now().time()} расписание на сегодня \n{schedule}')



# Для команды расписания на завтра
@bot.message_handler(func=lambda message: message.text.lower() == 'расписание на завтра')
def tomorrow_schedule(message):
    global schedule
    load_schedule_for_day('tomorrow')
    chat_id = message.chat.id
    if schedule_tomorrow() == "Воскресенье":
        bot.send_message(chat_id, "Завтра воскресенье. Расписания нет.")
    else:
        if schedule == 'Замен на завтра нет.':
            os.remove('replacement_tomorrow.txt')

            conn, cursor = get_connection()
            tomorrow_schedule(message)
            cursor.execute('''
                    UPDATE replacements
                    SET has_replacement = 0
                    WHERE day = Завтра AND week_type = нечетная
                ''')
            close_connection()

    bot.send_message(chat_id, f"Завтра \n {schedule}")
    print(f'расписание отправлено пользователю {chat_id}, в {datetime.datetime.now().time()} расписание на завтра \n{schedule}')


def get_morning_message():
    load_schedule_for_day('today')
    print(schedule)
    sleep(3)
    return schedule


def get_evening_message():
    load_schedule_for_day('tomorrow')
    print(schedule)
    sleep(3)
    return schedule


def print_message_at_time(target_hour, target_minute, message_function):
    global schedule
    # Функция для ожидания времени и вывода сообщения в консоль
    while True:
        now = datetime.datetime.now()
        target_time = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)

        # Если время уже прошло, устанавливаем на следующий день
        if now > target_time:
            target_time += datetime.timedelta(days=1)

        time_to_wait = (target_time - now).total_seconds()
        time.sleep(time_to_wait)  # Задержка до нужного времени

        # Получаем сообщение из переданной функции
        to_send()
        print(f"расписание отправлено, \nВремя: {datetime.datetime.now().strftime('%H:%M:%S')} {schedule}")


def to_send():
    global schedule
    conn, cursor = get_connection()
    cursor.execute("SELECT * FROM users WHERE notifications = 1")
    users = cursor.fetchall()
    for user in users:
        user_data = {
            "user_id": user[0],
            'chat_id': user[1],
            'admin_level': user[2],
            'notofications': user[3]
        }
        try:
            # Попытка отправить сообщение
            bot.send_message(user_data['user_id'], f'{schedule}')
        except telebot.apihelper.ApiTelegramException as e:
            # Логируем ошибку, если chat_id не найден
            logging.error(f"Не удалось отправить сообщение пользователю {user_data['user_id']}: {e}")
        except Exception as e:
            # Общая ошибка
            logging.error(f"Ошибка при отправке сообщения: {e}")


def delete_replacement():
    if os.path.exists('replacement_tomorrow.txt'):
        os.remove('replacement_tomorrow.txt')
        conn, cursor = get_connection()
        cursor.execute("INSERT OR REPLACE INTO replacements (day, week_type, has_replacement) VALUES (?, ?, ?)",
            ("Сегодня", get_week_type(datetime.date.today().isocalendar()[1]), 0))
        conn.commit()
        close_connection(conn, cursor)


def wait_for_target_time(target_hour, target_minute):
    while True:
        now = datetime.datetime.now()
        target_time = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)

        # Если текущее время уже прошло, устанавливаем целевое время на следующий день
        if now > target_time:
            target_time += datetime.timedelta(days=1)

        # Рассчитываем, сколько секунд осталось до целевого времени
        time_to_wait = (target_time - now).total_seconds()
        print(f"Ожидаем {time_to_wait} секунд до следующего вызова.")
        time.sleep(time_to_wait)  # Ожидаем до нужного времени

        # Время пришло, вызываем функцию удаления замены
        delete_replacement()


def start_scheduled_messages():
    # Запуск двух потоков для вывода сообщения в 6:00 и 17:00
    Thread(target=print_message_at_time, args=(6, 0, get_morning_message())).start()  # 6:00 отправка уведомления что будет сегодня
    Thread(target=print_message_at_time, args=(17, 0, get_evening_message())).start()  # 17:00 отправка уведомления вечером что будет завтра
    Thread(target=wait_for_target_time, args=(14, 0)).start()  # 14.00 обновление таймера
    threading.Thread(target=monitor_server).start()     # Мониторинг сервера раз в 6 часов

# Функция для мониторинга сервера
def monitor_server():
    while True:
        try:
            bot.send_message(CHAT_ID, 'Отец, я живой')
            time.sleep(21600)  # Ждать 6 часов, чтобы уведомить создателя, что бот работает
        except Exception as e:
            print('Ошибка при отправке уведомления что бот активен')
# Запуск
current_time = datetime.datetime.now().time()
setup_database()
start_scheduled_messages()
# bot.remove_webhook()

# Основной цикл
while True:
    try:
        # Запуск бота
        bot.polling(none_stop=True, interval=0)

    except Exception as e:
        # #Логируем ошибку
        # error_message = f"Ошибка при запуске polling: {str(e)}\n{traceback.format_exc()}"
        # logging.error(error_message)
        # # Отправляем уведомление в Telegram
        # send_error_notification(error_message)

        # Ждем 5 секунд перед перезапуском
        time.sleep(5)
