"""Utils for the learning module."""

import os
import subprocess

import requests


def autotag():
    """This adds a tag to the wandb run marking the commit number, allows versioning of experiments. From CleanRL's benchmark utility."""

    def _autotag() -> str:
        wandb_tag = ""
        print("autotag feature is enabled")
        try:
            git_tag = subprocess.check_output(["git", "describe", "--tags"]).decode("ascii").strip()
            wandb_tag = f"{git_tag}"
            print(f"identified git tag: {git_tag}")
        except subprocess.CalledProcessError:
            return wandb_tag

        git_commit = subprocess.check_output(["git", "rev-parse", "--verify", "HEAD"]).decode("ascii").strip()
        try:
            # try finding the pull request number on github
            prs = requests.get(f"https://api.github.com/search/issues?q=repo:Farama-Foundation/momaland+is:pr+{git_commit}")
            if prs.status_code == 200:
                prs = prs.json()
                if len(prs["items"]) > 0:
                    pr = prs["items"][0]
                    pr_number = pr["number"]
                    wandb_tag += f",pr-{pr_number}"
            print(f"identified github pull request: {pr_number}")
        except Exception as e:
            print(e)

        return wandb_tag

    if "WANDB_TAGS" in os.environ:
        raise ValueError(
            "WANDB_TAGS is already set. Please unset it before running this script or run the script with --auto-tag False"
        )
    wandb_tag = _autotag()
    if len(wandb_tag) > 0:
        os.environ["WANDB_TAGS"] = wandb_tag
