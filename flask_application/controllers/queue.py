from flask import Blueprint, render_template, get_template_attribute, flash, request, redirect, url_for, abort, jsonify
from flask.ext.security import (
    login_required, roles_required, roles_accepted, current_user)
from mongoengine import Q
from flask.ext.mongoengine.wtf import model_form

from flask_application import app
from flask_application.models import *

from ..forms import QueueForm, QueuedThingForm


from ..permissions.queue import *
app.jinja_env.globals['can_edit_queue'] = can_edit_queue
app.jinja_env.globals['can_add_to_queue'] = can_add_to_queue
app.jinja_env.globals['can_remove_from_queue'] = can_remove_from_queue
app.jinja_env.globals['can_edit_queued_thing'] = can_edit_queued_thing
app.jinja_env.globals['can_view_queued_thing'] = can_view_queued_thing


# Set up blueprint
# Although reading could also be watching or listening, the variable will be called "reading"
# The url prefix can (@todo!) be set in the application configuration so
# urls are like "/listening/groups"
queue = Blueprint('queue', __name__, url_prefix='/reading')


def current_user_queues():
    return Queue.objects.filter(creator=current_user.get_id())
app.jinja_env.globals['current_user_queues'] = current_user_queues


# views

@queue.route('/lists')
@queue.route('/lists/<int:page>')
def list(page=1):
    """
    See a list of queues
    """
    test = CreatorMixin()
    queues = Queue.objects.paginate(page=page, per_page=10)
    return render_template('queue/list.html',
                           title='All Lists',
                           queues=queues.items,
                           pagination=queues)


@queue.route('/list/add', methods=['GET', 'POST'])
def add():
    """
    Add a new queue
    """
    form = QueueForm(exclude=['creator'])
    if form.validate_on_submit():
        model = Queue()
        form.populate_obj(model)
        model.save()
        flash("Queue created")
        return redirect(url_for("queue.detail", id=model.id))
    return render_template('queue/add.html',
                           title='Start a new List',
                           form=form
                           )


@queue.route('/list/<id>')
def detail(id):
    """
    See a queue in more detail
    """
    queue = Queue.objects.get_or_404(id=id)
    return render_template('queue/detail.html',
                           queue=queue)


@queue.route('/list/<id>/edit', methods=['GET', 'POST'])
def edit(id):
    """
    Edit a queue
    """
    model = Queue.objects.get_or_404(id=id)
    if not can_edit_queue(model):
        abort(403)
    form = QueueForm(formdata=request.form, obj=model, exclude=['creator'])
    if form.validate_on_submit():
        model.title = form.title.data
        model.short_description = form.short_description.data
        model.description = form.description.data
        model.save()
        flash("Queue updated")
        return redirect(url_for("queue.detail", id=model.id))
    return render_template('queue/edit.html',
                           title='Edit %s' % model.title,
                           form=form)


@queue.route('/list/<id>/rearrange', methods=['POST'])
def rearrange(id):
    """
    Edit a queue
    """
    model = Queue.objects.get_or_404(id=id)
    if not can_edit_queue(model):
        abort(403)
    weights = {}
    weight = 1
    f = request.form
    for key in f.keys():
        for value in f.getlist(key):
            if key == 'o[]':
                weights[value.encode('utf-8').strip()] = weight
                weight = weight + 1
    model.set_weights(weights)
    return jsonify({'message': 'hello'})


@queue.route('/list/<id>/add/<thing_id>')
@queue.route('/list/<id>/add/<thing_id>/<ajax>')
def add_thing(id, thing_id, ajax=False):
    """
    Add a thing into a queue
    """
    q = Queue.objects.get_or_404(id=id)
    if not can_add_to_queue(q):
        abort(403)
    t = Thing.objects.get_or_404(id=thing_id)
    q.add_thing(t)
    if ajax:
        return jsonify({
            'message': 'Added to <a href="%s">%s</a>' % (url_for('queue.detail', id=q.id), q.title),
            'result': 'success',
        })
    else:
        return redirect(url_for("queue.detail", id=q.id))


@queue.route('/list/<id>/remove/<item_id>')
def remove_thing(id, item_id):
    q = Queue.objects.get_or_404(id=id)
    qt = QueuedThing.objects.get_or_404(id=item_id)
    if not can_remove_from_queue(q):
        abort(403)
    q.remove_thing(qt)
    flash("%s was removed" % qt.thing.title)
    return redirect(url_for("queue.detail", id=q.id))


@queue.route('/list/<id>/finish/<item_id>')
def finish_thing(id, item_id):
    q = Queue.objects.get_or_404(id=id)
    qt = QueuedThing.objects.get_or_404(id=item_id)
    if not can_remove_from_queue(q):
        abort(403)
    q.finish_thing(qt)
    flash("%s marked as finished!" % qt.thing.title)
    return redirect(url_for("queue.detail", id=q.id))


@queue.route('/list/<id>/unfinish/<item_id>')
def unfinish_thing(id, item_id):
    q = Queue.objects.get_or_404(id=id)
    qt = QueuedThing.objects.get_or_404(id=item_id)
    if not can_remove_from_queue(q):
        abort(403)
    q.unfinish_thing(qt)
    flash("%s no longer marked as finished" % qt.thing.title)
    return redirect(url_for("queue.detail", id=q.id))


@queue.route('/list/<id>/edit/<item_id>', methods=['GET', 'POST'])
def edit_thing(id, item_id):
    q = Queue.objects.get_or_404(id=id)
    qt = QueuedThing.objects.get_or_404(id=item_id)
    if not can_edit_queued_thing(q, qt):
        abort(403)
    form = QueuedThingForm(formdata=request.form, obj=qt, exclude=['creator'])
    if form.validate_on_submit():
        qt.subtitle = form.subtitle.data
        qt.short_description = form.short_description.data
        qt.description = form.description.data
        qt.accessibility = form.accessibility.data
        qt.save()
        flash("Notes on %s updated" % qt.thing.title)
        return redirect(url_for("queue.detail_thing", id=q.id, item_id=qt.id))
    return render_template('queue/edit_thing.html',
                           title='Notes on: ',
                           thing=qt.thing,
                           form=form)


@queue.route('/list/<id>/<item_id>')
def detail_thing(id, item_id):
    """
    See a queue in more detail
    """
    q = Queue.objects.get_or_404(id=id)
    qt = QueuedThing.objects.get_or_404(id=item_id)
    if not can_view_queued_thing(q, qt):
        abort(403)
    title = qt.thing.title
    if qt.subtitle:
        title = qt.subtitle
    return render_template('queue/detail_thing.html',
                           queue=q,
                           queued_thing=qt,
                           title=title)


# reading/now - list dates and what people are reading
# reading/in/public - lists all posts that have been filled out and marked
# as public

# reading/list/<id>/<id> - view a queued item
