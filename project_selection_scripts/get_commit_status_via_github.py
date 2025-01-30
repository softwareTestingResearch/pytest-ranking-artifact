import os
import requests
import json
import pandas as pd
import gzip
import time
import datetime

import const
from token_pool import TokenPool

TOKENPOOL = TokenPool()

COMMIT_STATUS_URL = "https://api.github.com/repos/{slug}/commits/{sha}/status"


def get_commit_data_api(slug, sha):
    github_url = COMMIT_STATUS_URL.format(slug=slug, sha=sha)
    try:
        headers = TOKENPOOL.get_next_token()
        html_response = requests.get(url=github_url, headers=headers)
        info = json.loads(html_response.text)
        while "state" not in info and "message" in info:
            print("message:", info["message"])
            print("API rate limit exceeded, sleep for 60s")
            print("current time:", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            time.sleep(60)
            TOKENPOOL.refresh_pool()
            headers = TOKENPOOL.get_next_token()
            html_response = requests.get(url=github_url, headers=headers)
            info = json.loads(html_response.text)
        return info
    except Exception as e:
        print("[ERROR] CANNOT GET SHA", github_url)
        return None


def get_commit_data(project, slug, sha, overwrite=False):
    out_dir = os.path.join(const.COMMITDIR, project, "commit_status")
    out_path = os.path.join(out_dir, f"{sha}.json.gz")
    if not os.path.exists(out_path) or overwrite:
        data = get_commit_data_api(slug, sha)
        if data:
            with gzip.open(out_path, "wt") as f:
                json.dump(data, f, indent=2)
    # else:
    #     print("collected", slug, sha)


def run(collect_random=False):
    """it does this for every collected commit
    https://docs.github.com/en/rest/commits/statuses?apiVersion=2022-11-28#about-commit-statuses"""
    prefix = "" if not collect_random else "random_"
    df = pd.read_csv(os.path.join(const.METADIR, prefix + "project_commits.csv"))
    for idx, row in df.iterrows():
        project = row["project"]
        slug = row["slug"]
        num_commits = row["num_commits"]
        print("processing", idx, project, slug, num_commits)

        os.makedirs(os.path.join(const.COMMITDIR, project, "commit_status"), exist_ok=True)
        commits = pd.read_csv(os.path.join(const.COMMITDIR, project, "commits.csv"))
        
        for idx_commits, row_commits in commits.iterrows():
            sha = row_commits["sha"]
            get_commit_data(project, slug, sha)


if __name__ == "__main__":
    run(collect_random=False)
    pass
