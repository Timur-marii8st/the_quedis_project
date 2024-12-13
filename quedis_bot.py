import logging
import sqlite3
import pandas as pd
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import asyncio

API_TOKEN = ''

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='Добавить группу'), KeyboardButton(text='Добавить предмет')],
        [KeyboardButton(text='Распределить темы'), KeyboardButton(text='Просмотреть баллы группы')],
        [KeyboardButton(text='Заменить выступающего')]
        ], resize_keyboard=True)

# waiting for love
waiting_for_subject_name = False
waiting_for_students_file = False
waiting_for_distributing = False
waiting_for_change = False

username = ''

# Функция для создания базы данных
async def create_database(file_path):
    try:
        data = pd.read_excel(file_path)
        column_headers = data.columns
        name = column_headers[0]

        data[name] = data[name].apply(lambda x: ' '.join(str(x).split()[:2]))

        conn = sqlite3.connect(f'{username}_sc.db')
        cur = conn.cursor()

        cur.execute(f'''
            CREATE TABLE IF NOT EXISTS StudentScores (
                {name} TEXT
            )''')

        data.to_sql('StudentScores', conn, if_exists='replace', index=False)

        conn.commit()
        conn.close()

        return 'База данных создана успешно!'
    except Exception as e:
        return f'Ошибка при создании базы данных: {e}'


@dp.message(lambda message: message.text == 'Добавить группу')
async def start(message: Message):
    global waiting_for_students_file
    global username
    username = message.from_user.username  # Присваиваем никнейм пользователя
    waiting_for_students_file = True
    await message.reply('Отправьте мне Excel-файл со списком студентов', reply_markup=main_keyboard)


# Хендлер для обработки отправки файла Excel
@dp.message(lambda message: message.document and waiting_for_students_file)
async def handle_excel(message: Message):
    document = message.document
    if document.mime_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
        global waiting_for_students_file
        file_path = f'downloads/{username}.xlsx'
        await bot.download(document, destination=file_path)
        result = await create_database(file_path)
        waiting_for_students_file = False
        await message.reply(result, reply_markup=main_keyboard)
    else:
        await message.reply('Пожалуйста, отправьте корректный Excel-файл (формат .xlsx).', reply_markup=main_keyboard)


# Функция для добавления нового столбца (учебной дисциплины)
async def add_subject(subject_name):
    try:
        conn = sqlite3.connect(f'{username}_sc.db')
        cur = conn.cursor()

        # Добавляем новый столбец для дисциплины
        cur.execute(f'ALTER TABLE StudentScores ADD COLUMN {subject_name} INTEGER DEFAULT 0')

        conn.commit()
        conn.close()
        return f'Дисциплина "{subject_name}" успешно добавлена!'
    except sqlite3.OperationalError:
        return f'Дисциплина "{subject_name}" уже существует в базе данных.'
    except Exception as e:
        return f'Ошибка при добавлении дисциплины: {e}'


# Хендлер для кнопки "Добавить предмет"
@dp.message(lambda message: message.text == 'Добавить предмет')
async def ask_for_subject_name(message: Message):
    global waiting_for_subject_name
    waiting_for_subject_name = True
    global username
    username = message.from_user.username
    await message.reply('Введите название новой учебной дисциплины.', reply_markup=main_keyboard)


# Хендлер для добавления новой дисциплины
@dp.message(lambda message: message.text and waiting_for_subject_name)
async def handle_subject(message: Message):
    global waiting_for_subject_name
    waiting_for_subject_name = False
    subject_name = message.text.strip().replace(' ', '_').lower()
    result = await add_subject(subject_name)
    await message.reply(result, reply_markup=main_keyboard)


@dp.message(lambda message: message.text == 'Распределить темы')
async def ask_for_distributing(message: Message):
    global waiting_for_distributing
    waiting_for_distributing = True
    global username
    username = message.from_user.username
    if username == '':
        await message.reply('Сначала добавьте группу, чтобы создать базу данных.', reply_markup=main_keyboard)
        return

    conn = sqlite3.connect(f'{username}_sc.db')
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info(StudentScores)")
    column_names = [f"{i} - {col[1]}" for i, col in enumerate(cur.fetchall())]
    column_names.pop(0)
    conn.close()

    await message.reply('\n'.join(column_names) + '\n\n Введите номер предмета и количество тем для группы через пробел', reply_markup=main_keyboard)


@dp.message(lambda message: message.text and waiting_for_distributing)
async def questions_distributing(message: Message):
    global waiting_for_distributing
    waiting_for_distributing = False

    try:
        subject_num, questions_num = map(int, message.text.strip().split())
    except ValueError:
        await message.reply('Пожалуйста, введите номер предмета и количество тем через пробел.', reply_markup=main_keyboard)
        return

    conn = sqlite3.connect(f'{username}_sc.db')
    cur = conn.cursor()

    cur.execute(f"PRAGMA table_info(StudentScores)")
    column_names = [col[1] for col in cur.fetchall()]
    subject = column_names[subject_num]

    query_select = f"""
        SELECT name, {subject}
        FROM StudentScores
        ORDER BY {subject} ASC
        LIMIT ?;
    """
    cur.execute(query_select, (questions_num,))
    results = cur.fetchall()

    for student in results:
        name, current_value = student
        query = f"UPDATE StudentScores SET {subject} = ? WHERE name == ?"
        cur.execute(query, (current_value + 1, name))

    conn.commit()
    conn.close()

    await message.reply(f'Назначено {len(results)} вопросов.', reply_markup=main_keyboard)


@dp.message(lambda message: message.text == 'Просмотреть баллы группы')
async def view_group(message: Message):
    global username
    username = message.from_user.username
    conn = sqlite3.connect(f'{username}_sc.db')
    cur = conn.cursor()

    table_name = "StudentScores"
    cur.execute(f"SELECT * FROM {table_name}")
    results = cur.fetchall()

    cur.execute(f"PRAGMA table_info({table_name})")
    columns = [col[1] for col in cur.fetchall()]

    conn.close()

    output = ""

    #вывод заголовков
    output += columns[0].ljust(27)
    for column in columns[1:]:
        output += column.rjust(16) + ' |'
    output += "\n"

    #вывод первого столбца
    for row in results:
        first_name = row[0].split()[0]
        output += first_name.ljust(32)
        name_len = len(first_name)

        #вывод остальных столбцов
        for cell in row[1:]:
            output += '| ' + str(cell).ljust(25 - name_len)
        output += "\n"

    await message.reply(f'{output}', reply_markup=main_keyboard)

@dp.message(lambda message: message.text == 'Заменить выступающего')
async def asking_for_change(message: Message):
    global waiting_for_change
    waiting_for_change = True
    global username
    username = message.from_user.username

    conn = sqlite3.connect(f'{username}_sc.db')
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info(StudentScores)")
    column_names = [f"{i} - {col[1]}" for i, col in enumerate(cur.fetchall())]
    column_names.pop(0)
    conn.close()

    await message.reply('\n'.join(column_names) + '\n\nВведите номер предмета и фамилию выступающего через пробел')

@dp.message(lambda message: message.text and waiting_for_change)
async def changing_student(message: Message):
    global waiting_for_change
    waiting_for_change = False
    global username
    username = message.from_user.username

    try:
        subject_num_str, pass_student_name = message.text.strip().split()
    except ValueError:
        await message.reply('Пожалуйста, введите номер предмета и имя вытсупающего пробел.', reply_markup=main_keyboard)
        return
    subject_num = int(subject_num_str)

    conn = sqlite3.connect(f'{username}_sc.db')
    cur = conn.cursor()

    cur.execute('''
                    SELECT name 
                    FROM StudentScores 
                    WHERE name LIKE ?
                ''', (f"{pass_student_name}%",))

    pass_student_row = cur.fetchone()
    if not pass_student_row:
        await message.reply('Студент не найден.')
        conn.close()
        return

    pass_student_name = pass_student_row[0]

    cur.execute(f"PRAGMA table_info(StudentScores)")
    column_names = [col[1] for col in cur.fetchall()]
    subject = column_names[subject_num]

    cur.execute(f'''
                    SELECT name 
                    FROM StudentScores 
                    ORDER BY {subject} ASC
                ''')
    new_student_row = cur.fetchone()

    if not new_student_row:
        await message.reply('Ошибка, Нет данных для обработки')
        conn.close()
        return

    new_student_name = new_student_row[0]

    student_changes = {
        pass_student_name: -1,
        new_student_name: +1
    }

    for student, score_change in student_changes.items():
        cur.execute(f'''
                        UPDATE StudentScores
                        SET {subject} = {subject} + ?
                        WHERE name = ?
                    ''', (score_change, student))

    conn.commit()
    conn.close()

    await message.reply(f'{pass_student_name} заменен на {new_student_name}.')


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())