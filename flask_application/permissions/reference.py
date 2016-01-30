from flask.ext.security import current_user


def can_edit_reference(reference):
    # Allow the creator of the thing to edit references in the thing
    if reference.thing and reference.thing.is_creator(current_user):
        return True
    # and also site editors as well as the creator of the actual reference
    return current_user.has_role('admin') or current_user.has_role('editor') or reference.is_creator(current_user)
