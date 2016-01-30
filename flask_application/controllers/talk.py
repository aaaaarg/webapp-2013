from flask import Blueprint, render_template, get_template_attribute, flash, request, redirect, url_for, abort, jsonify
from flask.ext.security import (
    login_required, roles_required, roles_accepted, current_user)
from mongoengine import Q
from flask.ext.mongoengine.wtf import model_form

from flask_application import app
from flask_application.models import *

from ..forms import ThreadForm, CommentForm

from ..permissions.talk import can_create_thread, can_create_comment
app.jinja_env.globals['can_create_thread'] = can_create_thread
app.jinja_env.globals['can_create_comment'] = can_create_comment

# Set up blueprint
talk = Blueprint('talk', __name__, url_prefix='/talk')


# -- jinja filters

@talk.app_template_filter()
def thread_origin_url(thread):
    """
    Returns a link to the collection, but includes ancestors if they exist
    """
    if not thread.origin:
        return ""
    if isinstance(thread.origin, Maker):
        return url_for('maker.detail', id=thread.origin.id)
    if isinstance(thread.origin, Collection):
        return url_for('collection.detail', id=thread.origin.id)
    if isinstance(thread.origin, Thing):
        return url_for('thing.detail', id=thread.origin.id)

# -- views below


@talk.route('/list')
@talk.route('/list/<int:page>')
def list(page=1):
    """
    See a list of comment threads
    """
    threads = Thread.objects.order_by(
        '-priority', '-last_comment').paginate(page=page, per_page=10)
    return render_template('talk/list.html',
                           title='All discussion',
                           threads=threads.items,
                           pagination=threads,
                           endpoint='talk.list')


@talk.route('/list/discussiononly')
@talk.route('/list/discussiononly/<int:page>')
def list_pure(page=1):
    """
    See a list of comment threads
    """
    threads = Thread.objects(origin__exists=False).paginate(
        page=page, per_page=10)
    return render_template('talk/list.html',
                           title='All discussion',
                           threads=threads.items,
                           pagination=threads,
                           endpoint='talk.list_pure')


@talk.route('/list/mine')
@talk.route('/list/mine/<int:page>')
def list_mine(page=1):
    """
    See a list of comment threads
    """
    threads = Thread.objects(comments__creator=current_user.get_id()).paginate(
        page=page, per_page=10)
    return render_template('talk/list.html',
                           title='Discussions with you',
                           threads=threads.items,
                           pagination=threads,
                           endpoint='talk.list_mine')


@talk.route('/<id>')
def thread(id):
    """
    See a comment thread
    """
    thread = Thread.objects.get_or_404(id=id)
    thread.populate_comment_creators()
    form = CommentForm(exclude=['creator'])
    return render_template('talk/detail.html',
                           thread=thread,
                           comments=thread.comments,
                           form=form)


@talk.route('/<id>/edit', methods=['GET', 'POST'])
def edit(id):
    """
    Edit a comment thread

    model = Thread.objects.get_or_404(id=id)
    if not can_edit_thread(model):
            abort(403)
    form = ThreadForm(formdata=request.form, obj=model, exclude=['creator'])
    if form.validate_on_submit():
            model.title = form.title.data
            model.short_description = form.short_description.data
            model.description = form.description.data
            model.save() 
            flash("Collection updated")
            return redirect(url_for("collection.detail", id=model.id))
    return render_template('collection/edit.html',
            title = 'Edit',
            form = form)
    """
    return 'edit page'


@talk.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """
    Add a new discussion thread
    """
    t = request.args.get('type', None)
    i = request.args.get('id', None)
    form = ThreadForm(exclude=['creator'], referenced_type=t, referenced_id=i)
    if form.validate_on_submit():
        thread = Thread()
        form.populate_obj(thread)
        thread.set_origin(form.referenced_type.data, form.referenced_id.data)
        thread.save()
        thread.add_comment(form.text.data)
        flash("Discussion created")
        return redirect(url_for("talk.list"))
    return render_template('talk/add.html',
                           title='Start a Discussion' if t is None else 'Add a Discussion',
                           form=form
                           )


@talk.route('/<id>/follow')
def follow(id):
    """
    Adds current user to follower of this comment thread
    Returns JSON
    """
    collection = Collection.objects.get_or_404(id=id)
    if not can_follow_collection(collection):
        return jsonify({
            'result': 'error',
            'message': 'Sorry!'})
    user = User.objects(id=current_user.id).first()
    collection.add_follower(user)
    return jsonify({
        'result': 'success',
        'message': unicode(get_template_attribute('collection/macros.html', 'unfollow')(collection))
    })


@talk.route('/<id>/unfollow')
def unfollow(id):
    """
    Removes current user as follower of this comment thread
    Returns JSON
    """
    collection = Collection.objects.get_or_404(id=id)
    if not can_unfollow_collection(collection):
        return jsonify({
            'result': 'error',
            'message': 'Sorry!'})
    user = User.objects(id=current_user.id).first()
    collection.remove_follower(user)
    return jsonify({
        'result': 'success',
        'message': unicode(get_template_attribute('collection/macros.html', 'follow')(collection))
    })


@talk.route('/<id>/comment/<comment_id>')
def comment(id, comment_id):
    """
    See a comment
    """
    collection = Collection.objects.get_or_404(id=id)
    return render_template('collection/detail.html',
                           collection=collection)


@talk.route('/<id>/comment/<comment_id>/edit')
def edit_comment(id, comment_id):
    """
    See a comment
    """
    collection = Collection.objects.get_or_404(id=id)
    return render_template('collection/detail.html',
                           collection=collection)


@talk.route('/<id>/comment/add', methods=['POST'])
@login_required
def add_comment(id):
    """
    Add a new comment to a thread
    """
    form = CommentForm(exclude=['creator'])
    thread = Thread.objects.get_or_404(id=id)
    if form.validate_on_submit():
        comment = Comment()
        thread.add_comment(form.text.data)
        flash("Added comment")
    return redirect(url_for("talk.thread", id=id))
