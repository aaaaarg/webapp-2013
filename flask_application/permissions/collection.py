from flask.ext.security import current_user


def can_add_collection():
    return current_user.is_authenticated()


def can_edit_collection(collection):
    return current_user.has_role('admin') or current_user.has_role('editor') or collection.is_creator(current_user) or collection.has_editor(current_user)


def can_delete_collection(collection):
    return current_user.has_role('admin') or current_user.has_role('editor') or collection.is_creator(current_user)

# In general can the user add things to collections. For specific cases,
# see below


def can_add_thing_to_collections():
    return current_user.is_authenticated()


# Send None for the thing to skip checking whether the collection has the
# thing (an expensive check)
def can_add_thing_to_collection(collection, thing=None):
    if thing and collection.has_thing(thing):
        return False
    if collection.accessibility == 'public':
        return current_user.is_active() and current_user.is_authenticated()
    elif collection.accessibility == 'semi-public':
        return current_user.has_role('admin') or current_user.has_role('editor') or collection.is_creator(current_user) or collection.has_editor(current_user)
    elif collection.accessibility == 'private':
        return current_user.has_role('admin') or current_user.has_role('editor') or collection.is_creator(current_user) or collection.has_editor(current_user)


def can_remove_thing_from_collection(collection, thing):
    if can_edit_collection(collection):
        return True
    return collection.added_thing(thing, current_user)


def can_follow_collection(collection):
    if collection.accessibility == 'private':
        return False
    if collection.has_follower(current_user):
        return False
    return True


def can_unfollow_collection(collection):
    if collection.has_follower(current_user):
        return True
    return False
