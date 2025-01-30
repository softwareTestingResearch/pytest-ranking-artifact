import datetime
import os
import re


def pr_number_in_run_title(title, pr_number):
    pr_number_title = title.split(";")[0].replace("syncpr=", "")
    try:
        if int(pr_number_title) == pr_number:
            return True
    except:
        pass
    return False


def timestring_to_timestamp(s: str) -> datetime.datetime:
    if "Z" in s:
        if "." in s:
            return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ")
        return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
    return datetime.datetime.strptime(s, "%Y-%m-%d")


def get_test_report_url(info, run_id, artifact_name):
    for art in info.get("artifacts", []):
        if art.get("name", "") == artifact_name:
            if art.get("workflow_run", {}).get("id", "") == run_id:
                return art.get("archive_download_url", None)
    return None


def compress_file(fpath):
    current_dir = os.path.dirname(os.path.realpath(__file__))
    folder, fname = os.path.dirname(fpath), os.path.basename(fpath)
    os.chdir(folder)
    os.system(f"zip -r {fname}.zip {fname}")
    os.chdir(current_dir)


def decompress_file(fpath):
    if not os.path.exists(fpath) and os.path.exists(fpath+".zip"):
        current_dir = os.path.dirname(os.path.realpath(__file__))
        folder, fname = os.path.dirname(fpath), os.path.basename(fpath)
        os.chdir(folder)
        os.system(f"unzip {fname}.zip")
        os.chdir(current_dir)


def get_modified_files_from_patch(patch: str):
    # modified_files = []
    # lines = patch.splitlines()
    # for line in lines:
    #     if line.startswith("diff --git "):
    #         print(line)
    #         matches = re.findall(r"diff --git \"?a\/.* \"?b\/(.*?)\"?\n", line, re.MULTILINE)
    #         print(matches)
    #         # Extract the file path after the a/ prefix
    #         # parts = line.strip().split(" b/")
    #         # diff --git a/... b/...
    #         # assert len(parts) == 2
    #         # file_path = parts[-1]
    #         modified_files += matches
    # return modified_files
    return re.findall(r"diff --git \"?a\/.* \"?b\/(.*?)\"?\n", patch, re.MULTILINE)



def commit_has_py_file_change(modified_files: list[str]) -> bool:
    for file in modified_files:
        if file.endswith(".py"):
            return True
    return False


def commit_has_ci_file_change(modified_files: list[str]) -> bool:
    for file in modified_files:
        if file.endswith("tox.ini") or ".github/workflows" in file:
            return True
    return False

def commit_has_test_ci_file_change(modified_files: list[str], test_workflow_files) -> bool:
    for file in modified_files:
        if file.endswith("tox.ini") or file in test_workflow_files:
            return True
    return False


if __name__ == "__main__":
    import glob
    fpaths = glob.glob("repos/*/rerun_test_build_scripts/*/*/*.patch")
    for fpath in fpaths:
        compress_file(fpath)
