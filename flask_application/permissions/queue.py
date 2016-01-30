from flask.ext.security import current_user


def can_edit_queue(queue):
    return current_user.has_role('admin') or current_user.has_role('editor') or queue.is_creator(current_user)


def can_add_to_queue(queue):
    return can_edit_queue(queue)


def can_remove_from_queue(queue):
    return can_edit_queue(queue)


def can_edit_queued_thing(queue, queued_thing):
    return can_edit_queue(queue)


def can_view_queued_thing(queue, queued_thing):
    if can_edit_queue(queue) or not queued_thing.accessibility == 'private':
        return True
    return False
