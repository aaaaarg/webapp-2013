#!/usr/bin/env python

import sys
import os

root_dir = os.path.normpath(os.path.abspath(os.path.dirname(__file__)))
os.chdir(root_dir)

# TODO: this should be moved into the wsgi file
activate_this = os.path.join(root_dir, 'venv2', 'bin', 'activate_this.py')
if os.path.exists(activate_this):
    execfile(activate_this, dict(__file__=activate_this))

sys.path.pop(0)
sys.path.insert(0, os.getcwd())

from flask_application import app
from flask.ext.script import Manager, Server

from flask_application.script import FixFilesMigration, Tweet, ESIndex, GetPath, ResetDB, PopulateDB, SolrReindex, FixMD5s, UploadSymlinks, IndexPDFText, ExtractISBN, BuildLibrary, AddToIpfsTest, ProcessIpfsAddOutput

from flask.ext.security.script import (CreateUserCommand, AddRoleCommand,
                                       RemoveRoleCommand, ActivateUserCommand, DeactivateUserCommand)

manager = Manager(app)
manager.add_command("runserver", Server())

manager.add_command("reset_db", ResetDB())
manager.add_command("populate_db", PopulateDB())

manager.add_command("solr_reindex", SolrReindex())
manager.add_command("es_index", ESIndex())

manager.add_command("get_path", GetPath())

manager.add_command("fix_md5s", FixMD5s())
manager.add_command("upload_symlinks", UploadSymlinks())

manager.add_command("pdf_extract", IndexPDFText())
manager.add_command("extract_isbn", ExtractISBN())
manager.add_command("build_library", BuildLibrary())

manager.add_command('create_user', CreateUserCommand())
manager.add_command('add_role', AddRoleCommand())
manager.add_command('remove_role', RemoveRoleCommand())
manager.add_command('deactivate_user', DeactivateUserCommand())
manager.add_command('activate_user', ActivateUserCommand())

manager.add_command('tweet', Tweet())

manager.add_command('add_to_ipfs_test', AddToIpfsTest())
manager.add_command('process_ipfs_add_output', ProcessIpfsAddOutput())

manager.add_command('fix_files_migration', FixFilesMigration())


if __name__ == "__main__":
    manager.run()
