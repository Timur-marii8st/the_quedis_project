import tkinter as tk
from tkinter import messagebox
import sqlite3
import pandas as pd

class QuedisApp:
    def __init__(self, root):
        self.root = root
        self.root.title('QUEDIS - управление баллами')
        self.root.geometry('500x500')

        self.label = tk.Label(root, text='Выберите действие:', font=('Arial', 16))
        self.label.pack(pady=20)

        self.options = [
            "Создание списка",
            "Распределение вопросов",
            "Просмотр группы и количества баллов",
            "Замена выступающего или выступившего"
        ]

        for option in self.options:
            button = tk.Button(
                root,
                text=option, command=lambda v=option: self.run_option(v)
            )
            button.pack(pady=5)

        self.quit_button = tk.Button(root, text='Выход', command=root.quit)
        self.quit_button.pack(pady=10)

    def run_option(self, v):
        choice = v
        if choice == "Создание списка":
            self.create_database()
        elif choice == "Распределение вопросов":
            self.assign_questions()
        elif choice == "Просмотр группы и количества баллов":
            self.view_group()
        elif choice == "Замена выступающего или выступившего":
            self.replace_student()
        else:
            messagebox.showwarning("Ошибка", "Выберите реальную опцию!")
            quit()

    def create_database(self):
        try:
            excel_table = 'student_excel_table.xlsx'
            data = pd.read_excel(excel_table)

            data['name'] = data['name'].apply(lambda x: ' '.join(str(x).split()[:2]))
            data['civil_law'] = 0
            data['criminal_law'] = 0
            data['labour_law'] = 0

            conn = sqlite3.connect('students_scores.db')
            cur = conn.cursor()

            cur.execute('''
                CREATE TABLE IF NOT EXISTS StudentScores (
                    name TEXT,
                    civil_law INTEGER,
                    criminal_law INTEGER,
                    labour_law INTEGER
                )''')

            data.to_sql("StudentScores", conn, if_exists="append", index=False)

            conn.commit()
            conn.close()

            messagebox.showinfo("Успех", "База данных создана успешно!")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Произошла ошибка: {e}")

    def assign_questions(self):
        def assign():
            subject_try = subject_var.get().lower()
            questions_number = int(questions_entry.get())

            if subject_try in civil_name_set:
                subject = 'civil_law'

            elif subject_try in criminal_name_set:
                subject = 'criminal_law'

            elif subject_try in labour_name_set:
                subject = 'labour_law'

            else:
                print('ошибка!')
                exit()

            conn = sqlite3.connect('students_scores.db')
            cur = conn.cursor()

            query_select = f"""
            SELECT name, {subject}
            FROM StudentScores
            ORDER BY {subject} ASC
            LIMIT ?;
            """
            cur.execute(query_select, (questions_number,))

            results = cur.fetchall()

            for student in results:
                name, current_value = student
                query = f"UPDATE StudentScores SET {subject} = ? WHERE name == ?"
                cur.execute(query, (current_value + 1, name))

            conn.commit()
            conn.close()

            messagebox.showinfo("Успех", f"Назначено вопросов: {len(results)}")
            assign_window.destroy()

        assign_window = tk.Toplevel(self.root)
        assign_window.title("Распределение вопросов")
        assign_window.geometry('400x200')

        tk.Label(assign_window, text='Введите предмет:').pack(pady=5)
        subject_var = tk.StringVar()
        tk.Entry(assign_window, textvariable=subject_var).pack(pady=5)

        tk.Label(assign_window, text='Количество вопросов:').pack(pady=5)
        questions_entry = tk.Entry(assign_window)
        questions_entry.pack(pady=5)

        tk.Button(assign_window, text='Назначить', command=assign).pack(pady=10)

    def view_group(self):
        conn = sqlite3.connect('students_scores.db')
        cur = conn.cursor()

        table_name = "StudentScores"
        cur.execute(f"SELECT * FROM {table_name}")
        results = cur.fetchall()

        cur.execute(f"PRAGMA table_info({table_name})")
        columns = [col[1] for col in cur.fetchall()]

        conn.close()

        output = ""

        output += columns[0].ljust(30) + '\t'
        for column in columns[1:]:
            output += column.rjust(14) + '\t'
        output += "\n"

        for row in results:
            first_name = row[0].split()[0]
            output += first_name.ljust(26) + '\t'

            for cell in row[1:]:
                output += str(cell).rjust(15) + '\t'
            output += "\n"

        messagebox.showinfo("Баллы студентов", output)

    def replace_student(self):
        def replace():
            subject_try = subject_var.get().lower()
            pass_student_name = pass_entry.get()

            if subject_try in civil_name_set:
                subject = 'civil_law'

            elif subject_try in criminal_name_set:
                subject = 'criminal_law'

            elif subject_try in labour_name_set:
                subject = 'labour_law'

            else:
                print('ошибка!')
                exit()

            conn = sqlite3.connect('students_scores.db')
            cur = conn.cursor()

            cur.execute('''
                SELECT name 
                FROM StudentScores 
                WHERE name LIKE ?
            ''', (f"{pass_student_name}%",))

            pass_student_row = cur.fetchone()
            if not pass_student_row:
                messagebox.showerror("Ошибка", "Студент не найден.")
                conn.close()
                return

            pass_student_name = pass_student_row[0]

            cur.execute(f'''
                SELECT name 
                FROM StudentScores 
                ORDER BY {subject} ASC
            ''')
            new_student_row = cur.fetchone()

            if not new_student_row:
                messagebox.showerror("Ошибка", "Нет данных для обработки.")
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

            messagebox.showinfo("Успех", f"{pass_student_name} заменен на {new_student_name}.")
            replace_window.destroy()

        replace_window = tk.Toplevel(self.root)
        replace_window.title("Замена студента")
        replace_window.geometry('400x200')

        tk.Label(replace_window, text='Введите предмет:').pack(pady=5)
        subject_var = tk.StringVar()
        tk.Entry(replace_window, textvariable=subject_var).pack(pady=5)

        tk.Label(replace_window, text='Фамилия пропустившего:').pack(pady=5)
        pass_entry = tk.Entry(replace_window)
        pass_entry.pack(pady=5)

        tk.Button(replace_window, text='Заменить', command=replace).pack(pady=10)

if __name__ == "__main__":

    civil_name_set = {'гп', 'гражданское право', 'гражданка', 'гражданское', 'civil', 'civil law'}
    criminal_name_set = {'уп', 'уголовное право', 'уголовка', 'уголовное', 'угаловное право', 'criminal',
                         'criminal law'}
    labour_name_set = {'тп', 'трудовое право', 'трудовое', 'трудовик', 'труд', 'labour', 'labour law'}

    root = tk.Tk()
    app = QuedisApp(root)
    root.mainloop()
