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
├── modified_ci_files_for_rerun_random_order.zip
├── project_meta.json
├── rerun_global_runs.py
├── rerun_random.py
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

`rerun_random`: rerun test-run builds from `lite_test_run_metadata.csv` for a specified project with random order.
It has the same CLI options as `rerun_global_runs`, and runs random order 10 times per build, each time using the new run ID as random seed.
For save compute budget, it only runs builds that have regression failures (as we do not need to construct the right RTP data cache before running the failed builds).
This script requires `eval_results/parsed_rerun_results/regression_failed_runs.json` as input, which lists the build IDs that contains regression failures (see [./eval_results](./eval_results/)).


`metrics`: compute APFD(c) metric values with one-to-one and many-to-one failure-to-fault mappings.

`main`: command wrapper to help run `rerun_global_runs`.

`modified_ci_files_for_rerun.zip`: contains the CI files we modified to run different orders on each evaluated project. The modifications aim to add support for `pytest-ranking` and pytest cache save/restore for GitHub Actions CI builds.


`modified_ci_files_for_rerun.zip`: contains the CI files we modified to run random order 10 runs per historical commit/build for each evaluated project, each time uses the new run ID as the random seed.


## Raw data from our rerun experiment

The raw data (4GB of CI log, JSON test report) of our reruns on all orders can be downloaded at [this link](https://drive.google.com/file/d/1osFBDosPCqmlkbkNGZ6dWA53lvhwkDM3/view?usp=sharing)

The raw data (1GB of CI log, JSON test report) of our reruns on 10 random order reruns can be downloaded at [this link](https://drive.google.com/file/d/1c-9SWRBmK3EILkXPQDViEPMk8VrJQInG/view?usp=sharing)

After downloading and decompressing the raw data into this directory, you may use the scripts from [./eval_results](./eval_results/) to further parse and analyze them.

If you wish to download the processed data instead (500MB in total), you may refer to [./eval_results/](./eval_results/).
