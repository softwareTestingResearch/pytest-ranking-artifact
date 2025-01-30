# README


## Folder content

```
.
├── README.md
├── download_global_runs_dataset.py
├── eval_results
│   ├── README.md
│   ├── analyze_rerun_results.py
│   └── parse_rerun_results.py
├── local_const.py
├── local_utils.py
├── main.py
├── metrics.py
├── modified_ci_files_for_rerun.zip
├── project_meta.json
├── rerun_global_runs.py
└── token_pool.py
```

## Description

`download_global_runs_datasets`: curate a list of historical GitHub Actions CI workflow test-run builds for projects specified in `project_meta.json`.
For each build, we collect the build metadata, commit metadata of the build, and repository content archive at the commit in zip format (*note that this can be storage-space-consuming*).
At the end, a dataset metadata csv file will be generated: `lite_test_run_metadata.csv`.

`rerun_global_runs`: rerun test-run builds from `lite_test_run_metadata.csv` for a specified project.
It support three CLI options: `setup`, `rerun`, and `download`, with an mandatory argument being the name of the project to be rerun.
Option `setup` sets up the repository and data folders which we will use to do the rerun and download run data.
Option `rerun` checks out code version of the to-be-rerun historical commit/build, and reruns it by pushing the checked-out changes via GitHub Actions CI workflow.
Option `download` downloads the build log and test report artifact of the completed GitHub Actions CI workflow runs.


`metrics`: compute APFD(c) metric values with one-to-one and many-to-one failure-to-fault mappings.

`main`: command wrapper to help run `rerun_global_runs`.

`modified_ci_files_for_rerun.zip`: contains the CI files we modified for each evaluated project, the modifications aim to add support for `pytest-ranking` and pytest cache save/restore for GitHub Actions CI builds.
