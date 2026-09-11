import os
from datetime import datetime

from flask import Blueprint, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from services.feedback_service import (
    FeedbackError,
    create_feedback,
    get_user_feedbacks,
    resolve_feedback,
)
from services.notify_service import get_badge_counts, mark_feedbacks_read
from services.authz import is_student_session

def create_feedback_blueprint(db_config, log_action, upload_folder, allowed_file):
    blueprint = Blueprint('feedback', __name__)

    @blueprint.route('/feedback')
    def feedback_list():
        if not is_student_session():
            return redirect(url_for('login_page'))

        username = session['username']
        feedbacks = get_user_feedbacks(db_config, username)
        # 进来就算看过了，清掉反馈角标
        mark_feedbacks_read(db_config, username)
        return render_template(
            'feedback/index.html',
            feedbacks=feedbacks,
            badges=get_badge_counts(db_config, username),
        )

    @blueprint.route('/feedback/submit', methods=['POST'])
    def feedback_submit():
        if not is_student_session():
            return redirect(url_for('login_page'))

        title = request.form.get('title')
        content = request.form.get('content')
        image_path = ''
        saved_image = None

        image = request.files.get('image')
        if image and image.filename:
            if not allowed_file(image.filename):
                return '图片格式不支持', 400

            original_stem, extension = os.path.splitext(image.filename)
            filename = f"{secure_filename(original_stem) or 'upload'}{extension.lower()}"

            stored_name = datetime.now().strftime('%Y%m%d_%H%M%S_%f_') + filename
            feedback_folder = os.path.join(upload_folder, 'feedback')
            os.makedirs(feedback_folder, exist_ok=True)
            saved_image = os.path.join(feedback_folder, stored_name)
            image.save(saved_image)
            image_path = f'static/uploads/feedback/{stored_name}'

        try:
            feedback_id = create_feedback(
                db_config,
                session['username'],
                title,
                content,
                image_path,
            )
        except FeedbackError as exc:
            if saved_image and os.path.exists(saved_image):
                os.remove(saved_image)
            return str(exc), exc.status_code
        except Exception:
            if saved_image and os.path.exists(saved_image):
                os.remove(saved_image)
            raise

        log_action('submit_feedback', 'feedback', feedback_id, f'title:{title}')
        return redirect(url_for('feedback.feedback_list'))

    @blueprint.route('/admin/reply_feedback/<int:fid>', methods=['POST'])
    def reply_feedback(fid):
        if session.get('identity') != 'admin':
            return '无管理员权限', 403

        try:
            resolve_feedback(db_config, fid, request.form.get('reply'))
        except FeedbackError as exc:
            return str(exc), exc.status_code

        log_action('reply_feedback', 'feedback', fid)
        return redirect(url_for('admin_panel'))

    return blueprint
