from flask import Blueprint, render_template

bp = Blueprint('web', __name__)

@bp.route('/')
def index():
    return render_template('index.html')
@bp.route('/settings')
def settings():
    return render_template('settings.html')
