import datetime
import glob
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from collections import defaultdict
from enum import Enum
from typing import List, Tuple

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

ACTION_RERUN = "rerun"
ACTION_SETUP = "setup"
ACTION_DOWNLOAD = "download"

WORKFLOW_SEARCH_URL = "https://api.github.com/repos/{slug}/actions/runs?&per_page=100&page={page_number}"


class ForkProject:
    def __init__(
            self,
            name: str,
            origin_slug: str,
            fork_slug: str,
            fork_branch: str,
            edited_ci_file_paths: List[str],
            wait_time_between_prs: int
            ) -> None:
        """
        edited_ci_file_paths: workflow files we edited
        wait_time_between_prs: minutes waited between pushing two PRs
        """
        self.name = name
        self.origin_slug = origin_slug
        self.fork_slug = fork_slug
        self.origin_clone_url = local_const.GITHUB_SSH_URL.format(slug=origin_slug)
        self.fork_clone_url = local_const.GITHUB_SSH_URL.format(slug=fork_slug)
        self.fork_branch = fork_branch
        self.ci_file_paths = edited_ci_file_paths
        self.wait_time_between_prs = wait_time_between_prs
        self.init_datafolders()

    def init_datafolders(self) -> None:
        """setup folders to store data for this project"""
        # make home folder for the project
        self.project_dir = os.path.join(local_const.RERUN_DIR, self.name)
        os.makedirs(self.project_dir, exist_ok=True)
        fork_codebase_dir = os.path.join(self.project_dir, "fork_codebase")
        self.codebase_dir = os.path.join(fork_codebase_dir, self.name)
        self.ci_file_backup_dir = os.path.join(self.project_dir, local_const.CI_FILE_BACKUP_DIR)
        self.workflowrun_dir = os.path.join(self.project_dir, local_const.WORKFLOWRUN_DIR)

    def setup(self) -> None:
        """Setup/Reset the local fork folder and ci_file_backup folder."""
        print("[global-run] Setting up")
        # Clean up the old fork clone.
        fork_codebase_dir = os.path.join(self.project_dir, "fork_codebase")
        if os.path.exists(fork_codebase_dir):
            os.system(f"rm -rf {fork_codebase_dir}/*")
        if os.path.exists(self.ci_file_backup_dir):
            os.system(f"rm -rf {self.ci_file_backup_dir}")

        # Create folders.
        os.makedirs(fork_codebase_dir, exist_ok=True)
        os.makedirs(self.ci_file_backup_dir, exist_ok=True)
        os.makedirs(self.workflowrun_dir, exist_ok=True)

        # Clone the project fork.
        current_dir = os.getcwd()
        os.chdir(fork_codebase_dir)
        os.system(f"git clone {self.fork_clone_url} {self.name}")
        os.chdir(current_dir)

        # Copy the CI files as backup.
        print("[global-run] Back up modified .github/workflows")
        os.chdir(self.codebase_dir)
        # Check out fork branch with modified CI files.
        os.system(f"git checkout {local_const.EDIT_CI_FILE_BRANCH}")
        os.system("git pull")
        # Backup modified CI files.
        os.system(f"cp -r .github/workflows {self.ci_file_backup_dir}")
        for file in self.ci_file_paths:
            file_dir = os.path.dirname(file)
            os.makedirs(os.path.join(self.ci_file_backup_dir, file_dir), exist_ok=True)
            os.system(f"cp {file} {self.ci_file_backup_dir}/{file}")

        # Checkout back to the default branch.
        os.system(f"git checkout {self.fork_branch}")

        # Back to script dir and finish.
        os.chdir(current_dir)

    def rerun(self, num_builds_to_run: int=100) -> None:
        """Rerun builds for a project.

        num_builds_to_run: number of builds to run.
        """
        # Load global test run dataset.
        df = pd.read_csv(os.path.join(local_const.GLOBAL_RUN_DATASET_DIR, "lite_test_run_metadata.csv"))
        # Rerun test run builds for the project.
        builds = df[df["project"] == self.name].to_dict("records")
        print(f"[global-run] Number of runs: {len(builds)}")
        for i, build in enumerate(builds):
            # Skip if this build bas been rerun.
            if self.has_rerun_results(build["run_id"]):
                continue
            # Submit first build.
            if i == 0:
                self.submit_build_to_rerun(build)
                continue
            #  Get the previous build info.
            is_overlap = check_overlap(builds[i-1], build)
            # Stop around given limit at a non-overlapping build.
            if i >= num_builds_to_run and not is_overlap:
                break
            if not is_overlap:
                # Simulate overlapping by starting them in parallel
                self.wait_till_all_previous_runs_finish()
            # Wait a bit before the next run, so that Github API result is updated.
            time.sleep(10)
            self.submit_build_to_rerun(build)

    def wait_till_all_previous_runs_finish(self) -> None:
        """Wait until all running github action builds are finished."""
        query = WORKFLOW_SEARCH_URL.format(slug=self.fork_slug, page_number=1)
        info = token_pool.query_info(TOKENPOOL, query)
        while has_running_workflow_runs(info):
            print("[global-run] Waiting running runs to finish.")
            time.sleep(60)
            # Query update info again.
            info = token_pool.query_info(TOKENPOOL, query)

    def submit_build_to_rerun(self, build: pd.Series) -> None:
        """Rerun a build."""
        print("\n[global-run] build info:", build)
        project = build["project"]
        run_id = build["run_id"]
        head_sha = build["head_sha"]
        run_conclusion = build["run_conclusion"]
        head_branch = build["head_branch"]

        # Reset codebase.
        self.reset_codebase_to_origin_head()

        # Remove everything but .git folder.
        print("\n[global-run] Reconstruct build commit")
        normal_files = glob.glob(os.path.join(self.codebase_dir, "*"))
        hidden_files = glob.glob(os.path.join(self.codebase_dir, ".*"))
        for file in normal_files + hidden_files:
            if os.path.basename(file) != ".git":
                os.system(f"rm -rf {file}")
        # Unzip {head_sha}.zip and copy all files to a temp folder.
        temp_extract_folder = os.path.join(self.project_dir, "temp_zip_extract")
        os.makedirs(temp_extract_folder, exist_ok=True)
        zip_file = os.path.join(local_const.GLOBAL_RUN_DATASET_DIR, "repo_zips", project, f"{head_sha}.zip")
        # Extract the zip file to a temporary folder.
        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
            zip_ref.extractall(temp_extract_folder)
        # Copy all files from the unzipped folder to the codebase folder.
        owner, project = self.origin_slug.split("/")
        head_sha_prefix = head_sha[:7]
        os.system(f"cp -r {temp_extract_folder}/{owner}-{project}-{head_sha_prefix}/. {self.codebase_dir}/")
        # Remove the temporary extraction folder.
        os.system(f"rm -rf {temp_extract_folder}/{owner}-{project}-{head_sha_prefix}")

        # Copy backed up .github/workflows to the codebase folder.
        os.makedirs(f"{self.codebase_dir}/.github/workflows", exist_ok=True)
        os.system(f"rm -rf {self.codebase_dir}/.github/workflows/*")
        os.system(f"cp -r {self.ci_file_backup_dir}/workflows/. {self.codebase_dir}/.github/workflows/")
        for file in self.ci_file_paths:
            # print(f"cp {self.ci_file_backup_dir}/{file} {self.codebase_dir}/{file}")
            os.system(f"cp {self.ci_file_backup_dir}/{file} {self.codebase_dir}/{file}")

        # Push this version of the code as commit.
        print("\n[global-run] Push code")
        current_dir = os.getcwd()
        os.chdir(self.codebase_dir)
        message = f"run_id={run_id}, outcome={run_conclusion}, bh={head_branch}, sha={head_sha}"
        os.system("git add .")
        os.system(f"git commit -m '{message}'")
        os.system(f"git push origin HEAD:{self.fork_branch} --force")
        os.chdir(current_dir)

    def reset_codebase_to_origin_head(self) -> None:
        current_dir = os.getcwd()
        os.chdir(self.codebase_dir)
        # Clean up any uncommitted changes.
        print("[global-run] Clean local changes in fork")
        os.system("git reset --hard")
        os.system("git clean -fd")
        os.system(f"git checkout {self.fork_branch}")

        # Reset the fork to origin.
        print("[global-run] Reset fork to origin")
        os.system(f"git remote add upstream {self.origin_clone_url}")
        os.system("git fetch upstream")
        os.system(f"git checkout {self.fork_branch}")
        os.system(f"git reset --hard upstream/{self.fork_branch}")
        # os.system(f"git push --force origin {self.fork_branch}")
        os.chdir(current_dir)

    def has_rerun_results(self, run_id: int) -> bool:
        artifact_files = [
            os.path.join(
                self.workflowrun_dir, str(int(run_id)), local_const.RUN_ARTIFACT_FILE.format(run_name=order)
            )
            for order in local_const.CI_WORKFLOW_NAMES
        ]
        return all(os.path.exists(file) for file in artifact_files)

    def download_rerun_results(self) -> None:
        """Download all completed reruns."""
        # Get a list of workflow reruns.
        print("[global-run] Get workflow rerun list")
        rerun_info = []
        for page_number in range(1, 1000):
            query = WORKFLOW_SEARCH_URL.format(slug=self.fork_slug, page_number=page_number)
            info = token_pool.query_info(TOKENPOOL, query)
            if len(info) < 1 or len(info["workflow_runs"]) < 1:
                break
            rerun_info += info["workflow_runs"]
        print(f"[global-run] Workflow rerun list length: {len(rerun_info)}")
        rerun_info = [run for run in rerun_info if "run_id" in run["display_title"] and run["name"] in local_const.CI_WORKFLOW_NAMES]
        # Sort reruns from most recent from the least.
        rerun_info.sort(key=lambda x: local_utils.timestring_to_timestamp(x["created_at"]).timestamp(), reverse=True)
        print(f"[global-run] Valid workflow rerun list length: {len(rerun_info)}")
        download_ordered_runs = set()
        for info in rerun_info:
            run_name = info["name"]
            origin_run_id = int(info["display_title"].split(", ")[0].replace("run_id=", ""))
            rerun_id = info["id"]
            rerun_conclusion = info["conclusion"]
            # Do not download for cancelled runs.
            if rerun_conclusion not in ["success", "failure"]:
                continue
            save_folder = os.path.join(self.workflowrun_dir, str(origin_run_id))
            os.makedirs(save_folder, exist_ok=True)
            # Skip if downloaded.
            if self.has_rerun_results(origin_run_id):
                continue
            # Skip if not the latest rerun.
            ordered_run_id = f"{origin_run_id} {run_name}"
            if ordered_run_id in download_ordered_runs:
                continue

            print(f"[global-run] Download {origin_run_id} {run_name}, rerun_id: {rerun_id}")
            download_ordered_runs.add(ordered_run_id)
            # Download workflow run metadata.
            run_meta_file = os.path.join(save_folder, local_const.RUN_META_FILE.format(run_name=run_name))
            with open(run_meta_file, "w") as f:
                json.dump(info, f, indent=2)
            # Download workflow run log as zip.
            log = token_pool.query_binary(
                mytokenpool=TOKENPOOL,
                myurl=local_const.CURL_RUN_LOG_URL.format(slug=self.fork_slug, run_id=rerun_id))
            run_log_file = os.path.join(save_folder, local_const.RUN_LOG_FILE.format(run_name=run_name))
            with open(run_log_file, "wb") as f:
                f.write(log)
            # Download workflow run artifact metadata.
            art_query = local_const.CURL_RUN_ARTIFACT_URL.format(slug=self.fork_slug, run_id=rerun_id)
            art_info = token_pool.query_info(TOKENPOOL, art_query)
            art_meta_file = os.path.join(save_folder, local_const.RUN_ARTIFACT_META_FILE.format(run_name=run_name))
            with open(art_meta_file, "w") as f:
                json.dump(art_info, f, indent=2)
            # Download artifact as zip.
            art_download_query = local_utils.get_test_report_url(art_info, rerun_id, local_const.ARTIFACT_NAME)
            if art_download_query is not None:
                art = token_pool.query_binary(mytokenpool=TOKENPOOL, myurl=art_download_query)
                art_file = os.path.join(save_folder, local_const.RUN_ARTIFACT_FILE.format(run_name=run_name))
                with open(art_file, "wb") as f:
                    f.write(art)


def has_running_workflow_runs(workflow_search_info) -> bool:
    running_states = ["in_progress", "queued", "requested", "waiting", "pending"]
    runs = workflow_search_info["workflow_runs"]
    for run in runs:
        if run["status"] in running_states:
            return True
    return False


def check_overlap(prev_build: dict, build: dict) -> bool:
    prev_build_updated_at  = local_utils.timestring_to_timestamp(prev_build["run_updated_at"]).timestamp()
    build_started_at = local_utils.timestring_to_timestamp(build["run_started_at"]).timestamp()
    return build_started_at < prev_build_updated_at


def run_project(project_info, actions: list):
    # Initialize project metadata.
    proj = ForkProject(
        name=project_info["name"],
        origin_slug=project_info["origin_slug"],
        fork_slug=project_info["fork_slug"],
        fork_branch=project_info["fork_branch"],
        edited_ci_file_paths=project_info["edited_ci_file_paths"],
        wait_time_between_prs=project_info.get("wait_time_minute", 1))

    if ACTION_SETUP in actions:
        proj.setup()

    if ACTION_RERUN in actions:
        proj.rerun()

    if ACTION_DOWNLOAD in actions:
        proj.download_rerun_results()


def runner():
    project_infos = json.load(open("project_meta.json", "r"))
    args = sys.argv
    if args[-2] not in project_infos or args[-1].split(",") == []:
        exit("Invalid command, example command: python3 run.py ipython setup")
    project_info = project_infos[args[-2]]
    actions = args[-1].split(",")
    print("[global-run] Running command", args[-2], actions)
    run_project(project_info, actions)


def rerun_single_build(project, run_id):
    project_infos = json.load(open("project_meta.json", "r"))
    project_info = project_infos[project]
    proj = ForkProject(
        name=project_info["name"],
        origin_slug=project_info["origin_slug"],
        fork_slug=project_info["fork_slug"],
        fork_branch=project_info["fork_branch"],
        edited_ci_file_paths=project_info["edited_ci_file_paths"],
        wait_time_between_prs=project_info.get("wait_time_minute", 1))
    df = pd.read_csv(os.path.join(local_const.GLOBAL_RUN_DATASET_DIR, "lite_test_run_metadata.csv"))
    # Rerun test run builds for the project.
    builds = df[df["project"] == project].to_dict("records")
    for build in builds:
        if str(build["run_id"]) == str(run_id):
            proj.submit_build_to_rerun(build)


if __name__ == "__main__":
    runner()
