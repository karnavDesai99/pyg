import argparse
import collections
import configparser
import hashlib
import os
import re
import sys
import zlib

argparser = argparse.ArgumentParser(description="content tracker")

# Handle subcommands (subparsers). i.e., commands like "commit" and "init" after the 
# initial "git" ("pyg" for this project) command.
# dest="command" means return the subparser as a string in the "command" field
argsubparsers = argparser.add_subparsers(title="Commands", dest="command")

# Subparsers are required. Just "pyg" is insufficient and useless.
# it has to be "py COMMAND" like "pyg commit" or "pyg add" 
argsubparsers.required = True

def main(argv=sys.argv[1:]):
    args = argparser.parse_args(argv)

    # Subparsers
    # "cmd_*" functions take the parsed args as parameter and proces and
    # validate them before executing the command 
    if   args.command == "add"         : cmd_add(args)
    elif args.command == "cat-file"    : cmd_cat_file(args)
    elif args.command == "checkout"    : cmd_checkout(args)
    elif args.command == "commit"      : cmd_commit(args)
    elif args.command == "hash-object" : cmd_hash_object(args)
    elif args.command == "init"        : cmd_init(args)
    elif args.command == "log"         : cmd_log(args)
    elif args.command == "ls-tree"     : cmd_ls_tree(args)
    elif args.command == "merge"       : cmd_merge(args)
    elif args.command == "rebase"      : cmd_rebase(args)
    elif args.command == "rev-parse"   : cmd_rev_parse(args)
    elif args.command == "rm"          : cmd_rm(args)
    elif args.command == "show-ref"    : cmd_show_ref(args)
    elif args.command == "tag"         : cmd_tag(args)

class Repository(object):
    worktree = None
    gitdir = None
    conf = None

    def __init__(self, path, force=False):
        self.worktree = path
        self.gitdir = os.path.join(path, ".git")
        if not (force or os.path.isdir(self.gitdir)):
            raise Exception("Not a Git repository %s" % path)

        # Read configuration file in .git/config
        self.conf = configparser.ConfigParser()
        cnf = repo_file(self, "config")
        if cnf and os.path.exists(cnf):
                self.conf.read([cnf])
        elif not force:
            raise Exception("Configuration file missing")
        if not force:
            vers = int(self.conf.get("core", "repositoryformatversion"))
            if vers != 0:
                raise Exception("Unsupported repositoryformatversion %s" % vers)
