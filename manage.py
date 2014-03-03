#!/usr/bin/env python

import sys, os
sys.path.pop(0)
sys.path.insert(0, os.getcwd())

from flask_application import app
from flask.ext.script import Manager, Server

from flask_application.script import ResetDB, PopulateDB, SolrReindex, MigrateMakers, MigrateUsers, MigrateInvitations, MigrateCollections, MigrateFollowers, MigrateComments, MigrateFiles, ProcessFiles, ProcessUploads, FixShortDescriptions

from flask.ext.security.script import (CreateUserCommand , AddRoleCommand,
        RemoveRoleCommand, ActivateUserCommand, DeactivateUserCommand)

manager = Manager(app)
manager.add_command("runserver", Server())

manager.add_command("reset_db", ResetDB())
manager.add_command("populate_db", PopulateDB())

manager.add_command("solr_reindex", SolrReindex())

manager.add_command("migrate_makers", MigrateMakers())
manager.add_command("migrate_users", MigrateUsers())
manager.add_command("migrate_invitations", MigrateInvitations())
manager.add_command("migrate_collections", MigrateCollections())
manager.add_command("migrate_followers", MigrateFollowers())
manager.add_command("migrate_comments", MigrateComments())
manager.add_command("migrate_files", MigrateFiles())
manager.add_command("process_files", ProcessFiles())
manager.add_command("process_uploads", ProcessUploads())
manager.add_command("fix_short_descriptions", FixShortDescriptions())

manager.add_command('create_user', CreateUserCommand())
manager.add_command('add_role', AddRoleCommand())
manager.add_command('remove_role', RemoveRoleCommand())
manager.add_command('deactivate_user', DeactivateUserCommand())
manager.add_command('activate_user', ActivateUserCommand())

if __name__ == "__main__":
    manager.run()
