import io
from flask import (Blueprint, render_template, redirect, url_for,
                   request, flash, abort, send_file)
from flask_login import login_required, current_user

from ..models import db, Group, Student, Subject, Score, AssignmentLog
from ..services.distributor import (
    distribute_topics, replace_speaker,
    ensure_scores_for_subject, ensure_scores_for_student,
)
from ..services.excel import import_students, export_scores

groups_bp = Blueprint('groups', __name__)

ALLOWED_EXTENSIONS = {'xlsx'}


def _allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _get_group_or_404(group_id: int) -> Group:
    group = Group.query.get_or_404(group_id)
    if group.user_id != current_user.id:
        abort(403)
    return group


# ---------------------------------------------------------------------------
# Root redirect
# ---------------------------------------------------------------------------

@groups_bp.route('/')
@login_required
def index():
    return redirect(url_for('groups.list_groups'))


# ---------------------------------------------------------------------------
# Group CRUD
# ---------------------------------------------------------------------------

@groups_bp.route('/groups')
@login_required
def list_groups():
    groups = Group.query.filter_by(user_id=current_user.id).order_by(Group.created_at.desc()).all()
    return render_template('groups/list.html', groups=groups)


@groups_bp.route('/groups/new', methods=['GET', 'POST'])
@login_required
def new_group():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Введите название группы.', 'danger')
        else:
            group = Group(name=name, user_id=current_user.id)
            db.session.add(group)
            db.session.commit()
            flash(f'Группа «{name}» создана.', 'success')
            return redirect(url_for('groups.group_detail', group_id=group.id))
    return render_template('groups/new.html')


@groups_bp.route('/groups/<int:group_id>')
@login_required
def group_detail(group_id):
    group = _get_group_or_404(group_id)
    students = Student.query.filter_by(group_id=group_id).order_by(Student.name).all()
    subjects = Subject.query.filter_by(group_id=group_id).order_by(Subject.display_name).all()

    score_map = {}
    if students and subjects:
        student_ids = [s.id for s in students]
        subject_ids = [s.id for s in subjects]
        scores = Score.query.filter(
            Score.student_id.in_(student_ids),
            Score.subject_id.in_(subject_ids),
        ).all()
        score_map = {(sc.student_id, sc.subject_id): sc.value for sc in scores}

    return render_template(
        'groups/detail.html',
        group=group,
        students=students,
        subjects=subjects,
        score_map=score_map,
    )


@groups_bp.route('/groups/<int:group_id>/delete', methods=['POST'])
@login_required
def delete_group(group_id):
    group = _get_group_or_404(group_id)
    name = group.name
    db.session.delete(group)
    db.session.commit()
    flash(f'Группа «{name}» удалена.', 'info')
    return redirect(url_for('groups.list_groups'))


# ---------------------------------------------------------------------------
# Subjects
# ---------------------------------------------------------------------------

@groups_bp.route('/groups/<int:group_id>/subjects/add', methods=['POST'])
@login_required
def add_subject(group_id):
    group = _get_group_or_404(group_id)
    display_name = request.form.get('subject_name', '').strip()
    if not display_name:
        flash('Введите название предмета.', 'danger')
        return redirect(url_for('groups.group_detail', group_id=group_id))

    slug = display_name.lower().replace(' ', '_')

    existing = Subject.query.filter_by(group_id=group_id, slug=slug).first()
    if existing:
        flash(f'Предмет «{display_name}» уже существует.', 'warning')
        return redirect(url_for('groups.group_detail', group_id=group_id))

    subject = Subject(display_name=display_name, slug=slug, group_id=group_id)
    db.session.add(subject)
    db.session.flush()
    ensure_scores_for_subject(subject)
    db.session.commit()
    flash(f'Предмет «{display_name}» добавлен.', 'success')
    return redirect(url_for('groups.group_detail', group_id=group_id))


@groups_bp.route('/groups/<int:group_id>/subjects/<int:subject_id>/delete', methods=['POST'])
@login_required
def delete_subject(group_id, subject_id):
    group = _get_group_or_404(group_id)
    subject = Subject.query.get_or_404(subject_id)
    if subject.group_id != group_id:
        abort(403)
    db.session.delete(subject)
    db.session.commit()
    flash(f'Предмет «{subject.display_name}» удалён.', 'info')
    return redirect(url_for('groups.group_detail', group_id=group_id))


# ---------------------------------------------------------------------------
# Students — import / export
# ---------------------------------------------------------------------------

@groups_bp.route('/groups/<int:group_id>/import', methods=['POST'])
@login_required
def import_excel(group_id):
    group = _get_group_or_404(group_id)

    file = request.files.get('excel_file')
    if not file or file.filename == '':
        flash('Выберите файл для загрузки.', 'danger')
        return redirect(url_for('groups.group_detail', group_id=group_id))

    if not _allowed_file(file.filename):
        flash('Допустимый формат файла: .xlsx', 'danger')
        return redirect(url_for('groups.group_detail', group_id=group_id))

    replace = request.form.get('replace') == '1'
    try:
        count = import_students(group, file.stream, replace=replace)
        flash(f'Импортировано студентов: {count}.', 'success')
    except ValueError as e:
        flash(str(e), 'danger')

    return redirect(url_for('groups.group_detail', group_id=group_id))


@groups_bp.route('/groups/<int:group_id>/export')
@login_required
def export_excel(group_id):
    group = _get_group_or_404(group_id)
    data = export_scores(group)
    return send_file(
        io.BytesIO(data),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'{group.name}_баллы.xlsx',
    )


# ---------------------------------------------------------------------------
# Distribution — assign & replace
# ---------------------------------------------------------------------------

@groups_bp.route('/groups/<int:group_id>/distribute', methods=['POST'])
@login_required
def distribute(group_id):
    group = _get_group_or_404(group_id)
    subject_id = request.form.get('subject_id', type=int)
    count = request.form.get('count', type=int)

    if not subject_id or not count or count < 1:
        flash('Укажите предмет и корректное количество тем.', 'danger')
        return redirect(url_for('groups.group_detail', group_id=group_id))

    subject = Subject.query.get_or_404(subject_id)
    if subject.group_id != group_id:
        abort(403)

    try:
        assigned = distribute_topics(subject_id, count)
        names = ', '.join(s.name for s, _ in assigned)
        flash(f'Назначено {len(assigned)} студентам: {names}.', 'success')
    except ValueError as e:
        flash(str(e), 'danger')

    return redirect(url_for('groups.group_detail', group_id=group_id))


@groups_bp.route('/groups/<int:group_id>/replace', methods=['POST'])
@login_required
def replace(group_id):
    group = _get_group_or_404(group_id)
    subject_id = request.form.get('subject_id', type=int)
    outgoing_id = request.form.get('outgoing_student_id', type=int)

    if not subject_id or not outgoing_id:
        flash('Укажите предмет и студента для замены.', 'danger')
        return redirect(url_for('groups.group_detail', group_id=group_id))

    subject = Subject.query.get_or_404(subject_id)
    if subject.group_id != group_id:
        abort(403)

    try:
        outgoing, incoming = replace_speaker(subject_id, outgoing_id)
        flash(f'«{outgoing.name}» заменён на «{incoming.name}».', 'success')
    except ValueError as e:
        flash(str(e), 'danger')

    return redirect(url_for('groups.group_detail', group_id=group_id))


# ---------------------------------------------------------------------------
# Assignment history
# ---------------------------------------------------------------------------

@groups_bp.route('/groups/<int:group_id>/history')
@login_required
def history(group_id):
    group = _get_group_or_404(group_id)

    student_ids = [s.id for s in group.students]
    logs = (AssignmentLog.query
            .filter(AssignmentLog.student_id.in_(student_ids))
            .order_by(AssignmentLog.created_at.desc())
            .limit(200)
            .all())

    return render_template('groups/history.html', group=group, logs=logs)
