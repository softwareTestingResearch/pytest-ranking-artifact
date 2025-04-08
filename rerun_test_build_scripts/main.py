import json
import os
import sys

script_dir = os.path.dirname(__file__)
parent_dir = os.path.join(script_dir, "..", "")
local_dir = os.path.join(script_dir, "..", "sync_prs")
sys.path.append(parent_dir)
sys.path.append(local_dir)



def run_projects(command):
    project_infos = json.load(open("project_meta.json", "r"))
    for project in project_infos:
        os.system(f"python3 rerun_global_runs.py {project} {command}")
        # input(f"[global-run] Finish {project}, press enter to continue:")
        pass

def run_projects_random(command):
    project_infos = json.load(open("project_meta.json", "r"))
    for project in project_infos:
        os.system(f"python3 rerun_random.py {project} {command}")
        # input(f"[global-run] Finish {project}, press enter to continue:")
        pass

if __name__ == "__main__":
    run_projects(command="setup,rerun")
    run_projects(command="download")
    run_projects_random(command="setup,rerun")
    run_projects_random(command="download")
    pass
