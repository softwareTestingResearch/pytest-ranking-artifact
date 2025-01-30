import datetime
import gzip
import json
import os
import time

import const
import get_project_commit_stats
import pandas as pd
import requests
from token_pool import TokenPool

TOKENPOOL = TokenPool()

REPO_URL = "https://api.github.com/repos/{slug}"


def get_project_stats(collect_random=False):
    prefix = "" if not collect_random else "random_"
    df = pd.read_csv(os.path.join(const.METADIR, prefix + "project_candidate.csv"))
    for idx, row in df.iterrows():
        project = row["project"]
        github_url = row["github_url"]
        slug = get_project_commit_stats.get_slug_from_github_url(github_url)
        try:
            url = REPO_URL.format(slug=slug)
            headers = TOKENPOOL.get_next_token()
            html_response = requests.get(url=url, headers=headers)
            info = json.loads(html_response.text)
            if "id" in info:
                outf = os.path.join(const.REPOSTATSDIR, f"{project}.json")
                with open(outf, "w") as f:
                    json.dump(info, f, indent=2)
        except Exception as e:
            print(project, github_url, e)

def get_project_stats_df(collect_random=False):
    prefix = "" if not collect_random else "random_"
    df = pd.read_csv(os.path.join(const.METADIR, prefix + "project_candidate.csv"))
    ret = []
    for idx, row in df.iterrows():
        project = row["project"]
        stats_file = os.path.join(const.REPOSTATSDIR, f"{project}.json")
        if os.path.exists(stats_file):
            with open(stats_file, "r") as f:
                data = json.load(f)
                ret.append([project, data["stargazers_count"], data["size"], data["language"]])
    ret = pd.DataFrame(ret, columns=["project", "stars", "size", "language"])
    ret.to_csv(os.path.join(const.METADIR, prefix + "project_github_stats.csv"), index=False)


if __name__ == "__main__":
    get_project_stats(collect_random=False)
    get_project_stats_df(collect_random=False)
