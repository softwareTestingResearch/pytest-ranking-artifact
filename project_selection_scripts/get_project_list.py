import os
import requests
import logging
import json
from bs4 import BeautifulSoup
import pandas as pd
import re
import multiprocessing as mp
from google.cloud import bigquery

import const
from utils import try_default

GITHUB_URL_REGEX = r"https?://(www\.)?github\.com/[^/]+/[^/]+/?$"


def fetch_all_pypi_projects():
    logging.info("fetching all pypi projects")
    r = requests.get("https://pypi.org/simple/").text

    logging.info("parsing pypi projects")
    proj_names = [a.text for a in BeautifulSoup(r, "html.parser").find_all("a")]
    # Remove first and last element since they are empty strings (bf4 parsing)
    
    df = pd.DataFrame(proj_names, columns=["project"])
    df.to_csv(os.path.join(const.METADIR, "project_name.csv"), index=False)


def _get_pypi_metadata(project_name):
    """
    :project_name: PyPI project name
    :returns: (status, http_response_code, json)
    """
    try:
        response = requests.get(
            url=f"https://pypi.python.org/pypi/{project_name}/json",
            stream=True,
        )
        http_response_code = response.status_code
    except Exception as ex:
        return "fetching failed", "", type(ex)
    try:
        data = response.json()
    except Exception as ex:
        return "parsing failed", http_response_code, type(ex)
    return "successful", http_response_code, data


def _is_valid_github_url(github_url: str) -> bool:
    return re.match(GITHUB_URL_REGEX, github_url) is not None


def get_project_metadata_helper(project):
    # 4. Fetch PyPI details
    fetch_status, http_response_code, pypi_data = _get_pypi_metadata(project)
    pypi_classifiers = try_default(lambda: pypi_data["info"]["classifiers"])
    # latest_pypi_tag = try_default(lambda: _get_latest_pypi_tag(pypi_data))
    pypi_project_urls = try_default(lambda: pypi_data["info"]["project_urls"])
    pypi_version = try_default(lambda: pypi_data["info"]["version"])
    pypi_require_python = try_default(lambda: pypi_data["info"]["requires_python"])
    pypi_summary = try_default(lambda: pypi_data["info"]["summary"])
    pypi_keywords = try_default(lambda: pypi_data["info"]["keywords"])
    pypi_require_dist = try_default(lambda: pypi_data["info"]["requires_dist"])

    # # 5. Search for Github URL (+ redirect + to_lower)
    # github_url = try_default(
    #     lambda: [url for _, url in pypi_project_urls.items() if _is_valid_github_url(url)][0]
    # )
    # github_url = try_default(lambda: github_url.lower())
    # if redirect_github_urls:
    #     github_url, github_url_status = try_default(lambda: resolve_url(github_url))
    # else:
    #     github_url_status = None
    # github_url = try_default(lambda: github_url.lower())

    # 6. Fetch git tags
    # git_tags: str = try_default(lambda: _get_git_tags(github_url))

    # 7. match PyPI and git tag
    # matching_github_tag = try_default(
    #     lambda: _match_pypi_git_tag(pypi_version=latest_pypi_tag, git_tags=git_tags)
    # )
    ret = {
        "classifiers": pypi_classifiers, "project_urls": pypi_project_urls,
        "version": pypi_version, "requires_python": pypi_require_python,
        "summary": pypi_summary, "keywords": pypi_keywords,
        "require_dist": pypi_require_dist
    }
    print("processed", project)
    return project, ret


def get_pypi_project_download():
    # Note: depending on where this code is being run, you may require
    # additional authentication. See:
    # https://cloud.google.com/bigquery/docs/authentication/
    client = bigquery.Client()

    # You can also go to https://bigquery.cloud.google.com/table/bigquery-public-data:pypi.downloads
    query_job = client.query("""
        SELECT 
        file.project AS project,
        COUNT(*) AS num_downloads
        FROM 
        `bigquery-public-data.pypi.file_downloads`
        WHERE 
        -- file.project = 'pytest'
        -- Only query the last 30 days of history
        DATE(timestamp)
            BETWEEN DATE('2023-01-01') AND DATE('2023-12-31')
        GROUP BY 
        file.project""")
    
    
    # results = query_job.result()  # Waits for job to complete.
    df = query_job.to_dataframe()
    # for row in results:
    #     print("{} downloads".format(row.num_downloads))
    df.to_csv(os.path.join(const.METADIR, "project_num_downloads.csv"), index=False)


def get_project_metadata(limit=2500):
    """Get metadata for the top-K most downloaded projects"""
    df = pd.read_csv(os.path.join(const.METADIR, "project_num_downloads.csv"))
    # get metadata per project, starting from the most downloaded ones
    df = df.sort_values(by=["num_downloads"], ascending=False)
    print("number of projects", len(df))

    data = {}
    outf_path = os.path.join(const.METADIR, f"project_metadata_top{limit}.json")
    if os.path.exists(outf_path):
        with open(outf_path, "r") as f:
            data = json.load(f)
    
    projects = df["project"].values.tolist()
    projects = [x for x in projects if x not in data]
    print("number of to-be-collected projects", len(projects))
    
    project_lists = [projects[x:x + 100] for x in range(0, len(projects), 100)]
    for idx, project_list in enumerate(project_lists):
        if len(data) > 2500:
            break
        print("project list", idx)
        pool = mp.Pool(mp.cpu_count())
        ret = pool.map(get_project_metadata_helper, project_list)
        for project_name, project_data in ret:
            data[project_name] = project_data
        print("saving data for #projects", len(data))
        with open(outf_path, "w") as f:
            json.dump(data, f, indent=2)


def _check_require_pytest(require_dist):
    if require_dist:
        for dist in require_dist:
            if dist.startswith("pytest "):
                return True
    return False


def _check_require_randomly(require_dist):
    if require_dist:
        for dist in require_dist:
            if "pytest-randomly" in dist or "pytest-random-order" in dist:
                return True
    return False

def get_project_candidate_csv():
    metadata = json.load(open(os.path.join(const.METADIR, f"project_metadata_top2500.json")))
    df = pd.read_csv(os.path.join(const.METADIR, "project_num_downloads.csv"))
    rows = []
    for project, project_data in metadata.items():
        github_url = try_default(
            lambda: [url for _, url in project_data["project_urls"].items() if _is_valid_github_url(url)][0]
        )
        github_url = try_default(lambda: github_url.lower())
        requires_python_version = project_data["requires_python"]
        requires_python_version = requires_python_version.replace(' ', '') if requires_python_version else None
        require_pytest = _check_require_pytest(project_data["require_dist"])
        rows.append([project, github_url, requires_python_version, require_pytest])
    
    rows = pd.DataFrame(rows, columns=["project", "github_url", "requires_python_version", "require_pytest"])
    df = pd.merge(df, rows, how="inner", on=["project"])

    print("number of projects", len(df))
    df = df[df["require_pytest"] == True]
    print("number of projects require pytest", len(df))
    df = df.dropna()
    df = df.drop(columns=["require_pytest"])
    print("number of projects with github url and required python version", len(df))
    df = df.drop_duplicates(subset=["github_url"])
    print("number of project with distinct github url", len(df))
    df.to_csv(os.path.join(const.METADIR, "project_candidate.csv"), index=False)


def get_randomly_project_candidate_csv():
    metadata = json.load(open(os.path.join(const.METADIR, f"project_metadata_top2500.json")))
    df = pd.read_csv(os.path.join(const.METADIR, "project_num_downloads.csv"))
    rows = []
    for project, project_data in metadata.items():
        github_url = try_default(
            lambda: [url for _, url in project_data["project_urls"].items() if _is_valid_github_url(url)][0]
        )
        github_url = try_default(lambda: github_url.lower())
        requires_python_version = project_data["requires_python"]
        requires_python_version = requires_python_version.replace(' ', '') if requires_python_version else None
        require_pytest = _check_require_pytest(project_data["require_dist"])
        require_random = _check_require_randomly(project_data["require_dist"])
        rows.append([project, github_url, requires_python_version, require_pytest, require_random])
    
    rows = pd.DataFrame(rows, columns=["project", "github_url", "requires_python_version", "require_pytest", "require_random"])
    df = pd.merge(df, rows, how="inner", on=["project"])

    print("number of projects", len(df))
    df = df[(df["require_pytest"] == True) & (df["require_random"] == True)]
    print("number of projects require pytest", len(df))
    df = df.dropna()
    df = df.drop(columns=["require_pytest", "require_random"])
    print("number of projects with github url and required python version", len(df))
    df = df.drop_duplicates(subset=["github_url"])
    print("number of project with distinct github url", len(df))
    df.to_csv(os.path.join(const.METADIR, "random_project_candidate.csv"), index=False)

if __name__ == "__main__":
    # fetch_all_pypi_projects()
    get_pypi_project_download()
    get_project_metadata()
    get_project_candidate_csv()
    # get_randomly_project_candidate_csv()