from ..models import db, Score, Student, Subject, AssignmentLog


def distribute_topics(subject_id: int, count: int) -> list:
    """
    Выбирает `count` студентов с наименьшим баллом по заданному предмету,
    увеличивает каждый балл на 1 и логирует действие.

    Возвращает список (Student, новый_балл) для отображения результата.
    """
    scores = (Score.query
              .filter_by(subject_id=subject_id)
              .order_by(Score.value.asc())
              .limit(count)
              .all())

    assigned = []
    for score in scores:
        score.value += 1
        db.session.add(AssignmentLog(
            student_id=score.student_id,
            subject_id=subject_id,
            action='ASSIGN',
        ))
        assigned.append((score.student, score.value))

    db.session.commit()
    return assigned


def replace_speaker(subject_id: int, outgoing_student_id: int):
    """
    Уменьшает балл уходящего студента на 1.
    Увеличивает балл студента с наименьшим баллом на 1.
    Логирует оба события.

    Возвращает (outgoing_student, incoming_student) или raises ValueError.
    """
    outgoing_score = Score.query.filter_by(
        student_id=outgoing_student_id,
        subject_id=subject_id,
    ).first()
    if outgoing_score is None:
        raise ValueError('Балл для уходящего студента не найден.')

    # Находим входящего студента ДО изменения баллов (как в оригинале),
    # исключая уходящего — чтобы не вернуть того же студента.
    incoming_score = (Score.query
                      .filter_by(subject_id=subject_id)
                      .filter(Score.student_id != outgoing_student_id)
                      .order_by(Score.value.asc())
                      .first())
    if incoming_score is None:
        raise ValueError('Нет другого студента для замены.')

    outgoing_score.value -= 1

    incoming_score.value += 1

    db.session.add_all([
        AssignmentLog(student_id=outgoing_student_id, subject_id=subject_id, action='REPLACE_OUT'),
        AssignmentLog(student_id=incoming_score.student_id, subject_id=subject_id, action='REPLACE_IN'),
    ])
    db.session.commit()

    return outgoing_score.student, incoming_score.student


def ensure_scores_for_subject(subject: Subject):
    """
    При добавлении нового предмета создаёт Score(value=0) для каждого студента группы,
    у кого ещё нет записи.
    """
    existing_ids = {s.student_id for s in Score.query.filter_by(subject_id=subject.id).all()}
    new_scores = [
        Score(student_id=student.id, subject_id=subject.id, value=0)
        for student in subject.group.students
        if student.id not in existing_ids
    ]
    if new_scores:
        db.session.add_all(new_scores)
        db.session.commit()


def ensure_scores_for_student(student: Student):
    """
    При импорте нового студента создаёт Score(value=0) для каждого предмета группы,
    у кого ещё нет записи.
    """
    existing_ids = {s.subject_id for s in Score.query.filter_by(student_id=student.id).all()}
    new_scores = [
        Score(student_id=student.id, subject_id=subject.id, value=0)
        for subject in student.group.subjects
        if subject.id not in existing_ids
    ]
    if new_scores:
        db.session.add_all(new_scores)
        db.session.commit()
