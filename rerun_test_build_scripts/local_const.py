import os

dir_path = os.path.dirname(os.path.realpath(__file__))

RERUN_DIR = os.path.join(dir_path, "rerun_results")
os.makedirs(RERUN_DIR, exist_ok=True)
DOWNLOAD_REPO_DIR = os.path.join(dir_path, "download_repo_data")
CODEBASE_DIR = "fork_codebase"
CI_FILE_BACKUP_DIR = "ci_file_backup"
WORKFLOWRUN_DIR = "workflow_runs"

CURL_PR_URL = "https://api.github.com/repos/{slug}/pulls"
CURL_RUN_URL = "https://api.github.com/repos/{slug}/actions/runs"
CURL_RUN_LOG_URL = "https://api.github.com/repos/{slug}/actions/runs/{run_id}/logs"
CURL_RUN_ARTIFACT_URL = "https://api.github.com/repos/{slug}/actions/runs/{run_id}/artifacts"
POST_RUN_CANCEL_URL = " https://api.github.com/repos/{slug}/actions/runs/{run_id}/cancel"
GITHUB_WORKFLOW_DIR = ".github/workflows"
GITHUB_SSH_URL = "git@github.com:{slug}.git"

ARTIFACT_NAME = "pytest-ranking upload test report json"

# https://docs.github.com/en/rest/actions/workflow-runs?apiVersion=2022-11-28#list-workflow-runs-for-a-repository
INCOMPLETE_STATUS = ["in_progress", "queued", "requested", "waiting", "pending"]

WORKFLOW_TRIGGER_TAG = "prsync.{pr_number}"

EDIT_CI_FILE_BRANCH = "edited-ci-files"

# Headers to mimic the browser
GENERAL_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 \
    (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'
}

WF_DEFUALT = "pytest_default_order"
WF_RANDOM = "random_order"
WF_QTF = "qtf_order"
WF_RECENTFAIL = "recent_fail_order"
WF_CHANGEAWARE = "change_first_order"
WF_MIX = "mix_order"
CI_WORKFLOW_NAMES = [
    WF_DEFUALT,
    WF_RANDOM,
    WF_QTF,
    WF_RECENTFAIL,
    WF_CHANGEAWARE,
    WF_MIX
]

CI_WORKFLOW_MACRO = {
    WF_DEFUALT: 'Default',
    WF_RANDOM: 'Random',
    WF_QTF: 'QTF',
    WF_RECENTFAIL: 'RecentFail',
    WF_CHANGEAWARE: 'SimChgPath',
    WF_MIX: 'Hybrid',
}

CLOSED_PR_DATASET_DIR = os.path.join(dir_path, "closed_pr_dataset")
GLOBAL_RUN_DATASET_DIR = os.path.join(dir_path, "global_run_dataset")

RUN_META_FILE = "run_meta_{run_name}.json"
RUN_LOG_FILE = "run_log_{run_name}.zip"
RUN_ARTIFACT_META_FILE = "artifact_meta_{run_name}.json"
RUN_ARTIFACT_FILE = "artifact_{run_name}.zip"
