from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask.ext.login import current_user, login_required
from flask.ext.micropub import MicropubClient
from redwind.models import get_settings, PosseTarget
from redwind.extensions import db

posse = Blueprint('posse', __name__, url_prefix='/posse',)
micropub = MicropubClient(client_id='https://github.com/kylewm/redwind')


def register(app):
    app.register_blueprint(posse)
    micropub.init_app(app)


@posse.context_processor
def inject_settings_variable():
    return {
        'settings': get_settings()
    }


@posse.route('/')
@login_required
def index():
    return render_template('posse/index.jinja2')


@posse.route('/add', methods=['POST'])
@login_required
def add():
    me = request.form.get('me')
    state = '|'.join((request.form.get('style', ''),
                      request.form.get('name', '')))
    return micropub.authorize(me, scope='post', state=state)


@posse.route('/callback')
@micropub.authorized_handler
def callback(info):
    if info.error:
        flash('Micropub failure: {}'.format(info.error))
    else:
        flash('Micropub success! Authorized {}'.format(info.me))

    target = PosseTarget(
        me=info.me, name='New Target', style='microblog',
        micropub_endpoint=info.micropub_endpoint,
        access_token=info.access_token)
    current_user.posse_targets.append(target)
    db.session.commit()
    return redirect(url_for('.edit', target_id=target.id))


@posse.route('/edit', methods=['GET', 'POST'])
@login_required
def edit():
    if request.method == 'GET':
        target_id = request.args.get('target_id')
        target = PosseTarget.query.get(target_id)
        return render_template('posse/edit.jinja2', target=target)

    target_id = request.form.get('target_id')
    target = PosseTarget.query.get(target_id)
    target.name = request.form.get('name')
    target.style = request.form.get('style')
    db.session.commit()
    return redirect(url_for('.edit', target_id=target_id))


@posse.route('/delete', methods=['POST'])
@login_required
def delete():
    target_id = request.form.get('target_id')
    target = PosseTarget.query.get(target_id)
    db.session.delete(target)
    db.session.commit()
    return redirect(url_for('.index'))
