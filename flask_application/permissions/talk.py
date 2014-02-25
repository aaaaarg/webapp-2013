from flask.ext.security import current_user


def can_edit_thread(thread):
	return current_user.has_role('admin') or current_user.has_role('editor') or thread.is_creator(current_user)

def can_edit_comment(comment):
	return current_user.has_role('admin') or current_user.has_role('editor') or comment.is_creator(current_user)

def can_create_thread():
	return current_user.is_authenticated()

def can_create_comment(thread):	
	return current_user.is_authenticated()
