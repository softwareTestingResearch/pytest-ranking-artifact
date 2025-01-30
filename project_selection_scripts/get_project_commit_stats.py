import os
import requests
import json
import pandas as pd
import glob
import multiprocessing as mp
import subprocess

import const
from token_pool import TokenPool

TOKENPOOL = TokenPool()

COMMIT_STATUS_URL = "https://api.github.com/repos/{slug}/commits/HEAD~2/status"

GITHUB_HTTP_URL = "https://github.com/{slug}.git"

def get_project_head_status(slug):
    try:
        github_url = COMMIT_STATUS_URL.format(slug=slug)
        headers = TOKENPOOL.get_next_token()
        html_response = requests.get(url=github_url, headers=headers)
        info = json.loads(html_response.text)
        state = info.get("state", None)
        total_count = info.get("total_count", None)
        return state, total_count
    except:
        return None, None


def get_slug_from_github_url(github_url):
    github_url = github_url.strip("/")
    github_url = github_url.split("github.com/")[-1]
    return github_url
    # slug = ""
    # for i in range(len(github_url)):
    #     c = github_url[i]
    #     if c.isascii() or c in [".", "-", "_"]:
    #         slug += c
    # return slug
    # # The repository name can only contain ASCII letters, digits, and the characters ., -, and _.


def get_project_head_status_data(collect_random=False):
    """Check the commit status of a grandparent of the project HEAD,
    if the status is pending, it is most likely that the project 
    does not have commit status enabled, we can thus filter them out
    """
    prefix = "" if not collect_random else "random_"
    df = pd.read_csv(os.path.join(const.METADIR, prefix + "project_candidate.csv"))
    ret = []
    for idx, row in df.iterrows():
        project = row["project"]
        github_url = row["github_url"]
        slug = get_slug_from_github_url(github_url)
        commit_state, job_total_count = get_project_head_status(slug)
        print("processing", idx, project, github_url, slug, commit_state, job_total_count)
        ret.append([project, commit_state, job_total_count])
    
    ret = pd.DataFrame(ret, columns=["project", "head_grandparent_state", "head_grandparent_job_count"])
    ret.to_csv(os.path.join(const.METADIR, prefix + "project_head_status.csv"))


def get_project_commit_hist_helper(project, github_url, overwrite=True):
    # clone repo
    trunk = os.path.join(const.REPOBUFDIR, f"{project}_trunk")
    current_dir = os.path.dirname(os.path.realpath(__file__))
    if not os.path.exists(trunk):
        slug = get_slug_from_github_url(github_url)
        link = GITHUB_HTTP_URL.format(slug=slug)
        os.chdir(const.REPOBUFDIR)
        try:
            subprocess.check_output(f"git clone {link} {project}_trunk", timeout=60, shell=True)
        except Exception as e:
            print("[ERROR] UNABLE TO CLONE", project, e)
        os.chdir(current_dir)

    if os.path.exists(trunk):
        # get a list of commits
        os.chdir(trunk)
        output = ""
        try:
            output = subprocess.check_output(
                "git log --since=\"2024-01-01\" --pretty=format:\"%H,%at,%as\"", 
                shell=True)
            output = output.decode("utf-8", errors="ignore")
        except Exception as e:
            print("[ERROR] UNABLE TO GET COMMIT SHAS", e)
        os.chdir(current_dir)
        print(project, github_url, "output length", len(output))

        # save commit history into csv
        if output != "":
            project_commit_dir = os.path.join(const.COMMITDIR, project)
            os.makedirs(project_commit_dir, exist_ok=True)
            csv_outf = os.path.join(project_commit_dir, "commits.csv")
            if not os.path.exists(csv_outf) or overwrite:
                with open(csv_outf, "w") as f:
                    f.write("sha,timestamp,date\n")
                    f.write(output + "\n")

        # remove repo
        os.system(f"rm -rf {trunk}")
    pass


def get_project_commit_hist(collect_random=False):
    """Get commit sha and timestamp per project since 2023-01-01
    We omit projects that have no build status, i.e., status==pending, from the dataset
    https://docs.github.com/en/rest/commits/statuses?apiVersion=2022-11-28#get-the-combined-status-for-a-specific-reference
    """
    prefix = "" if not collect_random else "random_"
    df = pd.read_csv(os.path.join(const.METADIR, prefix + "project_head_status.csv"))
    df = df[df["head_grandparent_state"] != "pending"]
    df = df.dropna()
    print("number of projects to collect commit shas", len(df))
    candidate_df = pd.read_csv(os.path.join(const.METADIR, prefix + "project_candidate.csv"))
    df = pd.merge(df, candidate_df, how="left", on=["project"])
    df = df[["project", "github_url"]].values.tolist()
    pool = mp.Pool(mp.cpu_count())
    pool.starmap(get_project_commit_hist_helper, df)
    
    
def get_commit_stats_df(collect_random=False):
    """Compute number of commits collected per project
    Create a dataset file with columns:
      project, num_downloads, github_url, requires_python_version, num_commits 
    """
    prefix = "" if not collect_random else "random_"
    files = glob.glob(os.path.join(const.COMMITDIR, "*/commits.csv"))
    print("number of commit csv", len(files))
    df = []
    for file in files:
        project = file.split("/")[-2]
        temp = pd.read_csv(file)
        df.append([project, len(temp.index)])
    df = pd.DataFrame(df, columns=["project", "num_commits"])
    print("total number of commits", df["num_commits"].sum())

    candidate_df = pd.read_csv(os.path.join(const.METADIR, prefix + "project_candidate.csv"))
    candidate_df["slug"] = candidate_df["github_url"].apply(lambda x: get_slug_from_github_url(x))
    df = pd.merge(candidate_df, df, how="inner", on=["project"])
    df = df.sort_values(by=["num_downloads"], ascending=False)
    df.to_csv(os.path.join(const.METADIR, prefix + "project_commits.csv"), index=False)



if __name__ == "__main__":
    get_project_head_status_data(collect_random=False)
    get_project_commit_hist(collect_random=False)
    get_commit_stats_df(collect_random=False)
    pass

