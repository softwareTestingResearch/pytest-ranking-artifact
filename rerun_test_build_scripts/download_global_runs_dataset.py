"""Download a list of workflow runs (aka builds) as a globally-ordered list per project."""

import datetime
import glob
import json
import os
import subprocess
import sys
import time

import pandas as pd
import requests

script_dir = os.path.dirname(__file__)
parent_dir = os.path.join(script_dir, "..", "")
local_dir = os.path.join(script_dir, "..", "rerun_test_build_scripts")
sys.path.append(parent_dir)
sys.path.append(local_dir)

import local_const
import local_utils
import token_pool

TOKENPOOL = token_pool.TokenPool()
TODAY_STR = datetime.datetime.today().strftime('%Y-%m-%d')

# Github API.
WORKFLOW_SEARCH_URL = "https://api.github.com/repos/{slug}/actions/runs?created={date}&per_page=100&page={page_number}"
COMMIT_PATCH_URL = "https://github.com/{slug}/commit/{sha}.patch"
COMMIT_URL = "https://api.github.com/repos/{slug}/commits/{sha}"
# Seems that this link can download zip for sha on non-main-branches
COMMIT_REPO_ZIP_URL = "https://api.github.com/repos/{slug}/zipball/{sha}"

# Folder to store downloaded data.
DOWNLOAD_GLOBAL_RUNS_FOLDER = "download_global_runs"
DOWNLOAD_COMMITS_FOLDER = "download_commits"
DOWNLOAD_COMMIT_PATCHES_FOLDER = "download_commit_patches"

# Constants for downloading closed PRs
DATASET_START_DATE = "2024-01-01"
DATASET_END_DATE = "2024-12-01"
MAX_PAGE_LIMIT = 10000

def get_weeks_between_dates(start_date: str, end_date: str):
    # Convert input strings to datetime objects
    start = datetime.datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.datetime.strptime(end_date, '%Y-%m-%d')

    # Ensure start_date is the beginning of the week (Monday)
    start -= datetime.timedelta(days=start.weekday())

    # Ensure end_date is the end of the week (Sunday)
    end += datetime.timedelta(days=(6 - end.weekday()))

    # Initialize a list to store week start and end dates
    weeks = []

    # Iterate through weeks
    current_date = start
    while current_date <= end:
        week_start = current_date
        week_end = current_date + datetime.timedelta(days=6)
        weeks.append((week_start.strftime('%Y-%m-%d'), week_end.strftime('%Y-%m-%d')))
        current_date += datetime.timedelta(days=7)

    return weeks


def get_days_between_dates(start_date: str, end_date: str):
    # Convert input strings to datetime objects
    start = datetime.datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.datetime.strptime(end_date, '%Y-%m-%d')

    days = []
    current_date = start
    while current_date <= end:
        days.append(current_date.strftime('%Y-%m-%d'))
        current_date += datetime.timedelta(days=1)
    return days


def download_global_runs(slug: str, start_date: str=DATASET_START_DATE, end_date: str=DATASET_END_DATE) -> None:
    """Download metadata of all workflow runs within a date range."""
    print("Running " + slug)
    owner, project_name = slug.split("/")
    # Create folder to store downloaded metadata of workflow runs.
    save_folder = os.path.join(local_const.DOWNLOAD_REPO_DIR, project_name, DOWNLOAD_GLOBAL_RUNS_FOLDER)
    os.makedirs(save_folder, exist_ok=True)

    # Download list of closed PRs page by page (each page has 1000 PRs).
    dates = get_days_between_dates(start_date, end_date)
    for date in dates:
        for page_number in range(1, MAX_PAGE_LIMIT):
            save_file = os.path.join(save_folder, f"global_runs_{date}_page{page_number}.json")
            if os.path.exists(save_file):
                continue
            query = WORKFLOW_SEARCH_URL.format(slug=slug, date=date, page_number=page_number)
            info = token_pool.query_info(TOKENPOOL, query)
            # Will not save empty page.
            if len(info) < 1 or len(info["workflow_runs"]) < 1:
                break
            with open(save_file, "w") as f:
                json.dump(info, f, indent=2)
            print("Write to " + save_file)


def download_global_run_commits(slug: str) -> None:
    """Download data for commits in workflow runs."""
    owner, project_name = slug.split("/")
    # Load all downloaded runs, consider only those within the start and end date.
    shas = []
    run_files = glob.glob(os.path.join(local_const.DOWNLOAD_REPO_DIR, project_name, DOWNLOAD_GLOBAL_RUNS_FOLDER, "*.json"))
    for run_file in run_files:
        runs = json.load(open(run_file))["workflow_runs"]
        shas += [run["head_sha"] for run in runs]
    print(f"Running {project_name}, number of run files {len(run_files)}, number of workflow runs: {len(shas)}, number of unique run shas: {len(set(shas))}")
    shas = set(shas)

    # Download list of commits for PRs within date range.
    save_folder = os.path.join(local_const.DOWNLOAD_REPO_DIR, project_name, DOWNLOAD_COMMITS_FOLDER)
    os.makedirs(save_folder, exist_ok=True)
    for sha in shas:
        save_file = os.path.join(save_folder, f"{sha}.json")
        if os.path.exists(save_file):
            continue
        query = COMMIT_URL.format(slug=slug, sha=sha)
        info = token_pool.query_info(TOKENPOOL, query)
        # We write to a file even when there is no data.
        # if "sha" not in info:
        #     continue
        with open(save_file, "w") as f:
            json.dump(info, f, indent=2)
        print("Write to " + save_file)


def download_global_run_commit_patches(slug: str) -> None:
    """Download commit patches."""
    owner, project_name = slug.split("/")
    # Load all downloaded runs, consider only those within the start and end date.
    shas = []
    run_files = glob.glob(os.path.join(local_const.DOWNLOAD_REPO_DIR, project_name, DOWNLOAD_GLOBAL_RUNS_FOLDER, "*.json"))
    for run_file in run_files:
        runs = json.load(open(run_file))["workflow_runs"]
        shas += [run["head_sha"] for run in runs]
    print(f"Running {project_name}, number of run files {len(run_files)}, number of workflow runs: {len(shas)}, number of unique run shas: {len(set(shas))}")
    shas = set(shas)

    # Download list of commits for PRs within date range.
    save_folder = os.path.join(local_const.DOWNLOAD_REPO_DIR, project_name, DOWNLOAD_COMMIT_PATCHES_FOLDER)
    os.makedirs(save_folder, exist_ok=True)
    for sha in shas:
        save_file = os.path.join(save_folder, f"{sha}.patch")
        if os.path.exists(save_file):
            continue
        query = COMMIT_PATCH_URL.format(slug=slug, sha=sha)
        html_response = requests.get(url=query, headers=local_const.GENERAL_HEADERS, timeout=10)
        with open(save_file, "w") as f:
            f.write(html_response.text)
            # local_utils.compress_file(save_file)
            print("Write to " + save_file)


def runner_download_global_run_data():
    """Download meta, list of commits and their patches for global runs for all projects."""
    project_meta = json.load(open("project_meta.json", "r"))
    for _, meta in project_meta.items():
        slug = meta["origin_slug"]
        download_global_runs(slug)
        download_global_run_commits(slug)
        download_global_run_commit_patches(slug)


def build_workflow_run_dataset(slug: str) -> None:
    """Build csv with workflow run metadata."""
    df = []
    owner, project_name = slug.split("/")
    # Get test workflow files.
    test_workflow_files = json.load(open("workflow_files_2024-01-01_2024-12-01.json", "r"))[slug]
    # Get workflow runs.
    runs = []
    run_files = glob.glob(os.path.join(local_const.DOWNLOAD_REPO_DIR, project_name, DOWNLOAD_GLOBAL_RUNS_FOLDER, "*.json"))
    for run_file in run_files:
        runs += json.load(open(run_file))["workflow_runs"]
    print(f"Running {project_name}, number of run files {len(run_files)}, number of workflow runs: {len(runs)}")
    for i, run in enumerate(runs):
        if i % 2000 == 0:
            print(f"Processing {round(100 * i / len(runs), 2)}")
        run_id = run["id"]
        run_started_at = run["run_started_at"]
        run_updated_at = run["updated_at"]
        workflow_id = run["workflow_id"]
        head_branch = run["head_branch"]
        head_sha = run["head_sha"]
        workflow_file_path = run["path"]
        is_test_run = True if workflow_file_path in test_workflow_files else False
        run_event = run["event"]
        run_status = run["status"]
        run_conclusion = run["conclusion"]
        # Find parent sha of the commit of this run.
        parent_shas = []
        num_parent_shas = 0
        commit_file = os.path.join(local_const.DOWNLOAD_REPO_DIR, project_name, DOWNLOAD_COMMITS_FOLDER, f"{head_sha}.json")
        if os.path.exists(commit_file):
            commit_metadata = json.load(open(commit_file, "r"))
            if "parents" in commit_metadata:
                parent_shas = [parent["sha"] for parent in commit_metadata["parents"]]
                num_parent_shas = len(parent_shas)
        # Find commit change related info
        commit_patch_file = os.path.join(local_const.DOWNLOAD_REPO_DIR, project_name, DOWNLOAD_COMMIT_PATCHES_FOLDER, f"{head_sha}.patch")
        with open(commit_patch_file, "r") as f:
            patch_content = f.read()
            # Get list of modified files.
            modified_files = local_utils.get_modified_files_from_patch(patch_content)
            num_changed_files = len(modified_files)
            # print(modified_files)
            is_py_file_changed = local_utils.commit_has_py_file_change(modified_files)
            is_any_ci_file_changed = local_utils.commit_has_ci_file_change(modified_files)
            is_test_ci_file_changed = local_utils.commit_has_test_ci_file_change(modified_files, test_workflow_files)
        row = [
            project_name,
            run_id,
            workflow_id,
            run_started_at,
            run_updated_at,
            run_event,
            run_status,
            run_conclusion,
            head_branch,
            head_sha,
            num_changed_files,
            parent_shas,
            num_parent_shas,
            workflow_file_path,
            is_test_run,
            is_py_file_changed,
            is_any_ci_file_changed,
            is_test_ci_file_changed,
        ]
        df.append(row)
    return df


def runner_build_workflow_run_dataset() -> None:
    os.makedirs(local_const.GLOBAL_RUN_DATASET_DIR, exist_ok=True)
    df = []
    project_meta = json.load(open("project_meta.json", "r"))
    for _, meta in project_meta.items():
        slug = meta["origin_slug"]
        df += build_workflow_run_dataset(slug)
    df = pd.DataFrame(
        data=df,
        columns=[
            "project",
            "run_id",
            "workflow_id",
            "run_started_at",
            "run_updated_at",
            "run_event",
            "run_status",
            "run_conclusion",
            "head_branch",
            "head_sha",
            "num_changed_files",
            "parent_shas",
            "num_parent_shas",
            "workflow_file_path",
            "is_test_run",
            "is_py_file_changed",
            "is_any_ci_file_changed",
            "is_test_ci_file_changed",
        ]
    )
    # Sort all workflow runs.
    df = df.sort_values(["project", "run_started_at"], ascending=True)
    df.to_csv(os.path.join(local_const.GLOBAL_RUN_DATASET_DIR, "metadata.csv"), index=False)


def get_repo_test_workflow_file_name(slug: str, start_date: str=DATASET_START_DATE, end_date: str=DATASET_END_DATE) -> None:
    """Get the list of workflow file names of a repo in history."""
    owner, project = slug.split("/")
    # Clone and go to repo.
    current_folder = os.getcwd()
    os.system("rm -rf tmp_repos/")
    os.makedirs("tmp_repos", exist_ok=True)
    os.chdir("tmp_repos")
    os.system(f"git clone https://github.com/{slug}.git")
    os.chdir(project)
    # Get list of commits within the date range.
    workflow_files = []
    process = subprocess.Popen(f"git log --after='{start_date}' --before='{end_date}' --format=format:%H", stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True)
    output, err = process.communicate()
    shas = [s.strip() for s in output.split('\n')]
    print(f"Number of commits: {len(shas)}")
    # Get set of files in .github/workflows/ of all commits above.
    for sha in shas:
        os.system(f"git checkout {sha}")
        current_workflow_files = glob.glob(f".github/workflows/*")
        for wf in current_workflow_files:
            content = open(wf, "r").read()
            if "pytest" in content or "tox" in content:
                workflow_files.append(wf)
    workflow_files = list(set(workflow_files))
    os.chdir(current_folder)
    return workflow_files


def runner_test_workflow_file_names():
    data = {}
    project_meta = json.load(open("project_meta.json", "r"))
    for _, meta in project_meta.items():
        slug = meta["origin_slug"]
        data[slug] = get_repo_test_workflow_file_name(slug)
    with open(f"workflow_files_{DATASET_START_DATE}_{DATASET_END_DATE}.json", "w") as f:
        json.dump(data, f, indent=2)


def runner_build_global_test_run_dataset():
    """Filtering and get a global test run dataset from the metadata.csv."""
    df = pd.read_csv(os.path.join(local_const.GLOBAL_RUN_DATASET_DIR, "metadata.csv"))
    df = df[
        (df["is_test_run"] == True)
        & (df["run_conclusion"].isin(["success", "failure"]))
    ]
    df = df.sort_values(["project", "run_started_at"], ascending=True)
    print("Test runs:")
    print(df[["project", "run_id"]].groupby(["project"]).nunique().reset_index())
    df.to_csv(os.path.join(local_const.GLOBAL_RUN_DATASET_DIR, "test_run_metadata.csv"), index=False)


def runner_build_global_test_run_lite_dataset():
    """Filtering and get a lite global test run dataset from the test_run_metadata.csv.

    Get all failed builds, for each failed build, get the first non-overlapping success build before it.
     - some failed builds have the same non-overlapping success build before them.
    """
    df = pd.read_csv(os.path.join(local_const.GLOBAL_RUN_DATASET_DIR, "test_run_metadata.csv"))
    # Make sure zip exists.
    df["zip_exist"] = False
    for i, row in df.iterrows():
        zip_path = os.path.join(
            local_const.GLOBAL_RUN_DATASET_DIR,
            "repo_zips", df.iloc[i]["project"], df.iloc[i]["head_sha"] + ".zip"
        )
        df.at[i, "zip_exist"] = os.path.exists(zip_path)
    df = df[df["zip_exist"] == True]
    df.drop("zip_exist", axis=1, inplace=True)
    df = df.reset_index(drop=True)
    # Get lite test run dataset.
    projects = df["project"].drop_duplicates().values.tolist()
    indices = []
    for project in projects:
        # Get failed run indices.
        failed_run_indices = df[(df["project"] == project) & (df["run_conclusion"] == "failure")].index.values.tolist()
        # Get the last succeeded run indices per failed build.
        succeeded_run_indices = []
        for i in failed_run_indices:
            j = i
            while df.iloc[j]["run_conclusion"] == "failure" or local_utils.timestring_to_timestamp(df.iloc[j]["run_updated_at"]).timestamp() > local_utils.timestring_to_timestamp(df.iloc[i]["run_started_at"]).timestamp():
                j -= 1
            if df.iloc[j]["project"] == project:
                succeeded_run_indices.append(j)
        indices += (failed_run_indices + succeeded_run_indices)
    indices = sorted(list(set(indices)))
    lite = df.iloc[indices]
    print("Test runs:")
    print(lite[["project", "run_id"]].groupby(["project"]).nunique().reset_index())
    lite.to_csv(os.path.join(local_const.GLOBAL_RUN_DATASET_DIR, "lite_test_run_metadata.csv"), index=False)


def runner_download_repo_zip_for_global_test_run_datasets() -> None:
    df = pd.read_csv(os.path.join(local_const.GLOBAL_RUN_DATASET_DIR, "test_run_metadata.csv"))
    project_meta = json.load(open("project_meta.json", "r"))
    # Create folders for repo zip.
    save_folder = os.path.join(local_const.GLOBAL_RUN_DATASET_DIR, "repo_zips")
    os.makedirs(save_folder, exist_ok=True)
    for project in project_meta.keys():
        os.makedirs(os.path.join(save_folder, project), exist_ok=True)
    # Download repo zip.
    for i, row in df.iterrows():
        project = row["project"]
        run_id = row["run_id"]
        head_sha = row["head_sha"]
        slug = project_meta[project]["origin_slug"]
        save_file = os.path.join(save_folder, project, f"{head_sha}.zip")
        if os.path.exists(save_file):
            continue
        try:
            query = COMMIT_REPO_ZIP_URL.format(slug=slug, sha=head_sha)
            repo_zip = token_pool.query_binary(mytokenpool=TOKENPOOL, myurl=query)
            with open(save_file, "wb") as f:
                f.write(repo_zip)
                print(f"Writing {save_file}")
        except ValueError as _:
            print(f"Repo zip not found for {slug}, {run_id}, {head_sha}")


if __name__ == "__main__":
    runner_download_global_run_data()
    runner_test_workflow_file_names()
    runner_build_workflow_run_dataset()
    runner_build_global_test_run_dataset()
    runner_download_repo_zip_for_global_test_run_datasets()
    runner_build_global_test_run_lite_dataset()
    pass
