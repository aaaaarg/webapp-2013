from flask.ext.security import current_user


def can_add_thing():
    return current_user.is_authenticated()


def can_edit_thing(thing):
    return current_user.has_role('admin') or current_user.has_role('editor') or thing.is_creator(current_user)


def can_delete_thing(thing):
    # or thing.is_creator(current_user)
    return current_user.has_role('admin') or current_user.has_role('editor')


def can_view_file_for_thing(thing):
    return current_user.is_authenticated()


def can_add_file_to_thing(thing):
    return current_user.has_role('admin') or current_user.has_role('editor') or current_user.has_role('contributor')


def can_delete_file_from_thing(thing):
    return current_user.has_role('admin') or current_user.has_role('editor')
