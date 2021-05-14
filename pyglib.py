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
    #if   args.command == "add"         : cmd_add(args)
    if args.command == "cat-file"    : cmd_cat_file(args)
    elif args.command == "checkout"    : cmd_checkout(args)
    # elif args.command == "commit"      : cmd_commit(args)
    elif args.command == "hash-object" : cmd_hash_object(args)
    elif args.command == "init"        : cmd_init(args)
    elif args.command == "log"         : cmd_log(args)
    elif args.command == "ls-tree"     : cmd_ls_tree(args)
    # elif args.command == "merge"       : cmd_merge(args)
    # elif args.command == "rebase"      : cmd_rebase(args)
    elif args.command == "rev-parse"   : cmd_rev_parse(args)
    # elif args.command == "rm"          : cmd_rm(args)
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

# Compute path under repo's gitdir.
def repo_path(repo, *path):
    return os.path.join(repo.gitdir, *path)

# Compute path under repo's gitdir, but create dirname(*path) if 
# it is absent. Create directories only upto the last component
def repo_file(repo, *path, mkdir=False):
    if repo_dir(repo, *path[:-1], mkdir=mkdir):
        return repo_path(repo, *path)

# If mkdir, create *path if it is absent
def repo_dir(repo, *path, mkdir=False):
    path = repo_path(repo, *path)
    if os.path.exists(path):
        if (os.path.isdir(path)):
            return path
        else:
            raise Exception("Not a directory %s" % path)
    if mkdir:
        os.makedirs(path)
        return path
    else:
        return None

def create_repo(path):
    repo = Repository(path, True)
    # Ensure path doesn't exist, or is empty 
    if os.path.exists(repo.worktree):
        if not os.path.isdir(repo.worktree):
            raise Exception ("%s is not a directory!" % path)
        if os.listdir(repo.worktree):
            raise Exception("%s is not empty!" % path)
    else:
        os.makedirs(repo.worktree)
    assert(repo_dir(repo, "branches", mkdir=True))
    assert(repo_dir(repo, "objects", mkdir=True))
    assert(repo_dir(repo, "refs", "tags", mkdir=True))
    assert(repo_dir(repo, "refs", "heads", mkdir=True))
    with open(repo_file(repo, "description"), "w") as f:
        f.write("Unnamed repository; edit this file 'description' to name the repository.\n")
    with open(repo_file(repo, "HEAD"), "w") as f:
        f.write("ref: refs/heads/master\n")
    with open(repo_file(repo, "config"), "w") as f:
        config = repo_default_config()
        config.write(f)
    return repo

def repo_default_config():
    ret = configparser.ConfigParser()
    ret.add_section("core")
    ret.set("core", "repositoryformatversion", "0")
    ret.set("core", "filemode", "false")
    ret.set("core", "bare", "false")
    return ret

# PYG INIT
argsp = argsubparsers.add_parser("init", help="Initialize a new, empty repository.")
argsp.add_argument("path",metavar="directory",
                    nargs="?",default=".",
                    help="Repository location.")
def cmd_init(args):
    create_repo(args.path)
# /PYG INIT

def get_repo(path=".", required=True):
    path = os.path.realpath(path)
    if os.path.isdir(os.path.join(path, ".git")):
        return Repository(path)
    # If not returned, recurse in parent, if w
    parent = os.path.realpath(os.path.join(path, ".."))
    if parent == path:
        # Bottom case
        # os.path.join("/", "..") == "/":
        # If parent==path, then path is root.
        if required:
            raise Exception("No git directory.")
        else:
            return None
    # Recursive case
    return get_repo(parent, required)

class Object (object):
    repo = None
    def __init__(self, repo, data=None):
        self.repo=repo
        if data != None:
            self.deserialize(data)
    
    def serialize(self):
        # This function MUST be implemented by subclasses.
        # It must read the object's contents from self.data, 
        # a byte string, and to convert it into a meaningful representation.  
        # What exactly that means depends on each subclass.
        raise Exception("Not implemented")
    
    def deserialize(self, data):
        raise Exception("Not implemented")

# Read object object_id from Git repository repo.  
# Return an Object whose exact type depends on the object.
def read_object(repo, sha):
    path = repo_file(repo, "objects", sha[0:2], sha[2:])
    with open (path, "rb") as f:
        raw = zlib.decompress(f.read())
        # Read object type
        x = raw.find(b' ')
        fmt = raw[0:x]
        # Read and validate object size
        y = raw.find(b'\x00', x)
        size = int(raw[x:y].decode("ascii"))
        if size != len(raw)-y-1:
            raise Exception("Malformed object {0}: bad length".format(sha))
        # Pick constructor
        if   fmt==b'commit' : c=Commit
        elif fmt==b'tree'   : c=Tree
        elif fmt==b'tag'    : c=Tag
        elif fmt==b'blob'   : c=Blob
        else:
            raise Exception("Unknown type %s for object %s".format(fmt.decode("ascii"), sha))
        # Call constructor and return object
        return c(repo, raw[y+1:])

def get_object(repo, name, fmt=None, follow=True):
    return name

def write_object(obj, actually_write=True):
    # Serialize object data
    data = obj.serialize()
    # Add header
    result = obj.fmt + b' ' + str(len(data)).encode() + b'\x00' + data
    # Compute hash
    sha = hashlib.sha1(result).hexdigest()
    if actually_write:
        # Compute path
        path=repo_file(obj.repo, "objects", sha[0:2], sha[2:], mkdir=actually_write)
        with open(path, 'wb') as f:
            # Compress and write
            f.write(zlib.compress(result))
    return sha

class Blob(Object):
    fmt=b'blob'
    def serialize(self):
        return self.blobdata
    def deserialize(self, data):
        self.blobdata = data

# PYG CAT-FILE
argsp = argsubparsers.add_parser("cat-file",
                                 help="Provide content of repository objects")

argsp.add_argument("type",
                   metavar="type",
                   choices=["blob", "commit", "tag", "tree"],
                   help="Specify the type")

argsp.add_argument("object",
                   metavar="object",
                   help="The object to display")

def cmd_cat_file(args):
    repo = get_repo()
    cat_file(repo, args.object, fmt=args.type.encode())

def cat_file(repo, obj, fmt=None):
    obj = read_object(repo, get_object(repo, obj, fmt=fmt))
    sys.stdout.buffer.write(obj.serialize())
# /PYG CAT-FILE

# PYG HASH-OBJECT
argsp = argsubparsers.add_parser("hash-object",help="Compute object ID and optionally creates a blob from a file")

argsp.add_argument("-t",
                   metavar="type",
                   dest="type",
                   choices=["blob", "commit", "tag", "tree"],
                   default="blob",
                   help="Specify the type")

argsp.add_argument("-w",
                   dest="write",
                   action="store_true",
                   help="Actually write the object into the database")

argsp.add_argument("path",
                   help="Read object from <file>")

def cmd_hash_object(args):
    if args.write:
        repo = Repository(".")
    else:
        repo = None

    with open(args.path, "rb") as fd:
        sha = hash_object(fd, args.type.encode(), repo)
        print(sha)

def hash_object(fd, fmt, repo=None):
    data = fd.read()
    # Choose constructor depending on
    # object type found in header.
    if   fmt==b'commit' : obj=Commit(repo, data)
    elif fmt==b'tree'   : obj=Tree(repo, data)
    elif fmt==b'tag'    : obj=Tag(repo, data)
    elif fmt==b'blob'   : obj=Blob(repo, data)
    else:
        raise Exception("Unknown type %s!" % fmt)
    return write_object(obj, repo)
# /PYG HASH-OBJECT

def parse_map_with_msg(raw, start=0, dict=None):
    if not dict:
        dict = collections.OrderedDict()
        # dict=OrderedDict() cannot be taken as argument, otherwise
        # all calls to the functions will increase the length of the 
        # same dict infinitely 

    # Search for the next space and the next newline.
    space = raw.find(b' ', start)
    nl = raw.find(b'\n', start)

    # If space appears before newline, it is a keyword.

    # Base case
    # =========
    # If newline appears first (or there's no space at all, in which
    # case find returns -1), we assume a blank line.  A blank line
    # means the remainder of the data is the message.
    if (space < 0) or (nl < space):
        assert(nl == start)
        dict[b''] = raw[start+1:]
        return dict

    # Recursive case
    # ==============
    # Read a key-value pair and recurse for the next.
    key = raw[start:space]

    # Find the end of the value. Continuation lines begin with a
    # space, so we loop until we find a "\n" not followed by a space.
    end = start
    while True:
        end = raw.find(b'\n', end+1)
        if raw[end+1] != ord(' '): break

    # Grab the value
    # Also, drop the leading space on continuation lines
    value = raw[space+1:end].replace(b'\n ', b'\n')

    # Don't overwrite existing data contents
    if key in dict:
        if type(dict[key]) == list:
            dict[key].append(value)
        else:
            dict[key] = [ dict[key], value ]
    else:
        dict[key]=value

    return parse_map_with_msg(raw, start=end+1, dict=dict)

def map_with_msg_serialize(map_with_msg):
    ret = b''
    # Output fields
    for k in map_with_msg.keys():
        # Skip the message itself
        if k == b'': continue
        val = map_with_msg[k]
        # Normalize to a list
        if type(val) != list:
            val = [ val ]
        for v in val:
            ret += k + b' ' + (v.replace(b'\n', b'\n ')) + b'\n'
    ret += b'\n' + map_with_msg[b'']
    return ret

# PYG COMMIT
class Commit(Object):
    fmt=b'commit'
    def deserialize(self, data):
        self.map_with_msg = parse_map_with_msg(data)
    def serialize(self):
        return map_with_msg_serialize(self.map_with_msg)
# /PYG COMMIT

# PYG LOG
argsp = argsubparsers.add_parser("log", help="Display history of a given commit.")
argsp.add_argument("commit",
                   default="HEAD",
                   nargs="?",
                   help="Commit to start at.")

def cmd_log(args):
    repo = get_repo()

    print("digraph pyglog{")
    log_graphviz(repo, get_object(repo, args.commit), set())
    print("}")

def log_graphviz(repo, sha, seen):
    if sha in seen:
        return
    seen.add(sha)
    commit = read_object(repo, sha)
    assert (commit.fmt==b'commit')
    if not b'parent' in commit.map_with_msg.keys():
        # Base case: the initial commit.
        return
    parents = commit.map_with_msg[b'parent']
    if type(parents) != list:
        parents = [parents]
    for p in parents:
        p = p.decode("ascii")
        print ("c_{0} -> c_{1};".format(sha, p))
        log_graphviz(repo, p, seen)
# /PYG LOG

class Leaf(object):
    def __init__(self, mode, path, sha):
        self.mode = mode
        self.path = path
        self.sha = sha

def parse_one_node(raw, start=0):
    # Find the space terminator of the mode
    x = raw.find(b' ', start)
    assert(x-start == 5 or x-start==6)
    # Read the mode
    mode = raw[start:x]
    # Find the NULL terminator of the path
    y = raw.find(b'\x00', x)
    # and read the path
    path = raw[x+1:y]
    # Read the SHA and convert to an hex string
    sha = hex(
        int.from_bytes(
            raw[y+1:y+21], "big"))[2:] # hex() adds 0x in front. Not what is required.
    # Padding 0 if needed
    if len(sha) < 40:
        for _ in range(40 - len(sha)):
            sha = "0" + sha
    return y+21, Leaf(mode, path, sha)

def parse_tree(raw):
    pos = 0
    max = len(raw)
    ret = []
    while pos < max:
        pos, data = parse_one_node(raw, pos)
        ret.append(data)
    return ret

def serialize_tree(obj):
    #@FIXME Add serializer!
    ret = b''
    for i in obj.items:
        ret += i.mode
        ret += b' '
        ret += i.path
        ret += b'\x00'
        sha = int(i.sha, 16)
        # @FIXME Does
        ret += sha.to_bytes(20, byteorder="big")
    return ret

class Tree(Object):
    fmt=b'tree'
    def deserialize(self, data):
        self.items = parse_tree(data)
    def serialize(self):
        return serialize_tree(self)

# PYG LS-TREE
argsp = argsubparsers.add_parser("ls-tree", help="Pretty-print a tree object.")
argsp.add_argument("object",help="The object to show.")

def cmd_ls_tree(args):
    repo = get_repo()
    obj = read_object(repo, get_object(repo, args.object, fmt=b'tree'))
    for item in obj.items:
        print("{0} {1} {2}\t{3}".format(
            "0" * (6 - len(item.mode)) + item.mode.decode("ascii"),
            # Disply type of object being pointed to.
            read_object(repo, item.sha).fmt.decode("ascii"),
            item.sha,
            item.path.decode("ascii")))
# /PYG LS-TREE

# PYG CHECKOUT
argsp = argsubparsers.add_parser("checkout", help="Checkout a commit inside of a directory.")
argsp.add_argument("commit",
                   help="The commit or tree to checkout.")
argsp.add_argument("path",
                   help="The EMPTY directory to checkout on.")

def cmd_checkout(args):
    repo = get_repo()
    obj = read_object(repo, get_object(repo, args.commit))
    # If the object is a commit, get its tree
    if obj.fmt == b'commit':
        obj = read_object(repo, obj.map_with_msg[b'tree'].decode("ascii"))
    # Verify that path is an empty directory
    if os.path.exists(args.path):
        if not os.path.isdir(args.path):
            raise Exception("Not a directory {0}!".format(args.path))
        if os.listdir(args.path):
            raise Exception("Not empty {0}!".format(args.path))
    else:
        os.makedirs(args.path)
    checkout_tree(repo, obj, os.path.realpath(args.path).encode())

def checkout_tree(repo, tree, path):
    for item in tree.items:
        obj = read_object(repo, item.sha)
        dest = os.path.join(path, item.path)
        if obj.fmt == b'tree':
            os.mkdir(dest)
            checkout_tree(repo, obj, dest)
        elif obj.fmt == b'blob':
            with open(dest, 'wb') as f:
                f.write(obj.blobdata)
# /PYG CHECKOUT

# PYG SHOW-REF
def resolve_ref(repo, ref):
    with open(repo_file(repo, ref), 'r') as fp:
        # Leave out final \n
        data = fp.read()[:-1]
    if data.startswith("ref: "):
        return resolve_ref(repo, data[5:])
    else:
        return data

def list_refs(repo, path=None):
    if not path:
        path = repo_dir(repo, "refs")
    ret = collections.OrderedDict()
    # OrderedDict and sort the output of listdir to get sortes refs
    for f in sorted(os.listdir(path)):
        can = os.path.join(path, f)
        if os.path.isdir(can):
            ret[f] = list_refs(repo, can)
        else:
            ret[f] = resolve_ref(repo, can)
    return ret

argsp = argsubparsers.add_parser("show-ref", help="List references.")

def cmd_show_ref(args):
    repo = get_repo()
    refs = list_refs(repo)
    show_ref(repo, refs, prefix="refs")

def show_ref(repo, refs, with_hash=True, prefix=""):
    for k, v in refs.items():
        if type(v) == str:
            print ("{0}{1}{2}".format(
                v + " " if with_hash else "",
                prefix + "/" if prefix else "",
                k))
        else:
            show_ref(repo, v, with_hash=with_hash, prefix="{0}{1}{2}".format(prefix, "/" if prefix else "", k))
# /PYG SHOW-REF

# PYG TAG
class Tag(Commit):
    fmt = b'tag'

argsp = argsubparsers.add_parser(
    "tag",
    help="List and create tags")

argsp.add_argument("-a",
                    action="store_true",
                    dest="create_tag_object",
                    help="Whether to create a tag object")

argsp.add_argument("name",
                    nargs="?",
                    help="The new tag's name")

argsp.add_argument("object",
                    default="HEAD",
                    nargs="?",
                    help="The object the new tag will point to")

def create_tag(repo: Repository, name, reference, create_tag_object):
    # get the GitObject from the object reference
    sha = get_object(repo, reference)
    if create_tag_object:
        # create tag object (commit)
        tag = Tag(repo)
        tag.map_with_msg = collections.OrderedDict()
        tag.map_with_msg[b'object'] = sha.encode()
        tag.map_with_msg[b'type'] = b'commit'
        tag.map_with_msg[b'tag'] = name.encode()
        tag.map_with_msg[b'tagger'] = b'The soul eater <grim@reaper.net>'
        tag.map_with_msg[b''] = b'This is the commit message that should have come from the user\n'
        tag_sha = write_object(tag, repo)
        # create reference
        create_ref(repo, "tags/" + name, tag_sha)
    else:
        # create lightweight tag (ref)
        create_ref(repo, "tags/" + name, sha)

def create_ref(repo, ref_name, sha):
    with open(repo_file(repo, "refs/" + ref_name), 'w') as fp:
        fp.write(sha + "\n")

def cmd_tag(args):
    repo = get_repo()

    if args.name:
        create_tag(args.name,
                   args.object,
                   type="object" if args.create_tag_object else "ref")
    else:
        refs = list_refs(repo)
        show_ref(repo, refs["tags"], with_hash=False)
# /PYG TAG

def resolve_object(repo, name):
    # Resolve name to an object hash in repo.
    # This function has records:
    #   - the HEAD literal
    #   - short and long hashes
    #   - tags
    #   - branches
    #   - remote branches
    candidates = []
    hash_regex = re.compile(r"^[0-9A-Fa-f]{1,16}$")
    short_hash_regex = re.compile(r"^[0-9A-Fa-f]{1,16}$")
    # Abort if string is empty.
    if not name.strip():
        return None
    # Head is nonambiguous
    if name == "HEAD":
        return [resolve_ref(repo, "HEAD")]
    if hash_regex.match(name):
        if len(name) == 40:
            # This is a complete hash
            return [ name.lower() ]
        elif len(name) >= 4:
            # 4 is the min length for a short hash 
            name = name.lower()
            prefix = name[0:2]
            path = repo_dir(repo, "objects", prefix, mkdir=False)
            if path:
                rem = name[2:]
                for f in os.listdir(path):
                    if f.startswith(rem):
                        candidates.append(prefix + f)
    return candidates

def get_object(repo, name, fmt=None, follow=True):
    sha = resolve_object(repo, name)
    if not sha:
        raise Exception("No such reference {0}.".format(name))
    if len(sha) > 1:
        raise Exception("Ambiguous reference {0}: Candidates are:\n - {1}.".format(name,  "\n - ".join(sha)))
    sha = sha[0]
    if not fmt:
        return sha
    while True:
        obj = read_object(repo, sha)
        if obj.fmt == fmt:
            return sha
        if not follow:
            return None
        # Follow tags
        if obj.fmt == b'tag':
            sha = obj.map_with_msg[b'object'].decode("ascii")
        elif obj.fmt == b'commit' and fmt == b'tree':
            sha = obj.map_with_msg[b'tree'].decode("ascii")
        else:
            return None

# PYG REV-PARSE
argsp = argsubparsers.add_parser(
    "rev-parse",
    help="Parse revision (or other objects )identifiers")

argsp.add_argument("--wyag-type",
                   metavar="type",
                   dest="type",
                   choices=["blob", "commit", "tag", "tree"],
                   default=None,
                   help="Specify the expected type")

argsp.add_argument("name",
                   help="The name to parse")

def cmd_rev_parse(args):
    if args.type:
        fmt = args.type.encode()
    repo = get_repo()
    print (get_object(repo, args.name, args.type, follow=True))

class Index_Entry(object):
    ctime = None
    # The last time a file's metadata changed. This is a tuple (seconds, nanoseconds)
    mtime = None
    # The last time a file's data changed. This is a tuple (seconds, nanoseconds)
    dev = None
    # The ID of device containing this file
    ino = None
    # The file's inode number
    mode_type = None
    # The object type, either b1000 (regular), b1010 (symlink), b1110 (gitlink). 
    mode_perms = None
    # The object permissions, an integer.
    uid = None
    # User ID of owner
    gid = None
    # Group ID of owner
    size = None
    # Size of this object in bytes
    obj = None
    # The object's hash as a hex string
    flag_assume_valid = None
    flag_extended = None
    flag_stage = None
    flag_name_length = None
    # Length of the name if < 0xFFF, -1 otherwise

    name = None
                