from synctogit.config import BoolConfigItem, StrConfigItem

git_branch = StrConfigItem("git", "branch", "master")
git_push = BoolConfigItem("git", "push", False)
git_remote = StrConfigItem("git", "remote", None)
git_remote_name = StrConfigItem("git", "remote_name", "origin")
git_repo_dir = StrConfigItem("git", "repo_dir")
