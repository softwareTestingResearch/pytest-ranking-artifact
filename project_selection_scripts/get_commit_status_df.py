import datetime
import gzip
import json
import multiprocessing as mp
import os

import const
import pandas as pd


def str_to_timestamp(s):
    # 2023-02-09T07:22:06Z
    t = datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
    t = datetime.datetime.timestamp(t)
    return t

def collect_statuses_data_per_commit(statuses):
    ctx_start = str_to_timestamp(statuses[0]["created_at"])
    ctx_update = str_to_timestamp(statuses[0]["updated_at"])
    ctx_has_test_kw, ctx_has_ci_kw = False, False
    for status in statuses:
        ctx_start = min(ctx_start, str_to_timestamp(status["created_at"]))
        ctx_update = max(ctx_update, str_to_timestamp(status["updated_at"]))
        lowcap_context = status["context"].lower()
        # lowcap_desc = status["description"].lower()
        if "test" in lowcap_context:
            ctx_has_test_kw = True
        if "ci" in lowcap_context:
            ctx_has_ci_kw = True
        if "continuous integration" in lowcap_context:
            ctx_has_ci_kw = True
    return ctx_start, ctx_update, ctx_has_test_kw, ctx_has_ci_kw


def get_commit_status_stats(project, sha):
    state, ctx_start, ctx_update, num_ctx = None, None, None, None
    ctx_has_test_kw, ctx_has_ci_kw = None, None
    data_file = os.path.join(const.COMMITDIR, project, "commit_status", f"{sha}.json.gz")
    if os.path.exists(data_file):
        with gzip.open(data_file, "rt", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
            state = data.get("state", None)
            num_ctx = data.get("total_count", None)
            if "statuses" in data and len(data["statuses"]) > 0:
                ctx_start, ctx_update, ctx_has_test_kw, ctx_has_ci_kw = collect_statuses_data_per_commit(data["statuses"])
    return [state, num_ctx, ctx_start, ctx_update, ctx_has_test_kw, ctx_has_ci_kw]


def get_commit_status_df_helper(idx, project):
    """return [sha, timestamp, date, status, first_job_time, last_job_time]
    job means context in
    https://docs.github.com/en/rest/commits/statuses?apiVersion=2022-11-28#get-the-combined-status-for-a-specific-reference
    """
    print("processing", idx, project)
    df = pd.read_csv(os.path.join(const.COMMITDIR, project, "commits.csv"))
    shas = df["sha"].values.tolist()
    stats = []
    for sha in shas:
        row = get_commit_status_stats(project, sha)
        stats.append([sha] + row)
    stats = pd.DataFrame(
        stats,
        columns=["sha", "state", "num_job", "ctx_start", "ctx_update", "ctx_has_test_kw", "ctx_has_ci_kw"])
    df = pd.merge(df, stats, how="inner", on=["sha"])
    df.insert(0, "project", project)
    return df


def get_commit_status_df(collect_random=False):
    prefix = "" if not collect_random else "random_"
    """For each commit, get the status and duration"""
    df = pd.read_csv(os.path.join(const.METADIR, prefix + "project_commits.csv"))
    args = [(i, x) for i, x in enumerate(df["project"].values.tolist())]
    pool = mp.Pool(mp.cpu_count())
    dfs = pool.starmap(get_commit_status_df_helper, args)
    print("processing df")
    dfs = pd.concat(dfs, axis=0)
    df = pd.merge(df, dfs, how="right", on=["project"])
    df.to_csv(os.path.join(const.METADIR, prefix + "commit_status.csv"), index=False)


if __name__ == "__main__":
    get_commit_status_df(collect_random=False)
    pass
