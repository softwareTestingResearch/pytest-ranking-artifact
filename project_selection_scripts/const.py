import os

dir_path = os.path.dirname(os.path.realpath(__file__))


METADIR = os.path.join(dir_path, "metadata")
os.makedirs(METADIR, exist_ok=True)

COMMITDIR = os.path.join(dir_path, "commits")
os.makedirs(COMMITDIR, exist_ok=True)

REPOBUFDIR = os.path.join(dir_path, "repo_buffer")
os.makedirs(REPOBUFDIR, exist_ok=True)

REPOSTATSDIR = os.path.join(dir_path, "repo_stats")
# os.makedirs(REPOSTATSDIR, exist_ok=True)