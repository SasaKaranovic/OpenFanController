import subprocess

def get_git_long_hash() -> str:
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode('ascii').strip()
    except Exception as e:
        return f"Could not get gith hash: {e}"

def get_git_short_hash() -> str:
    try:
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()
    except Exception as e:
        return f"Could not get gith hash: {e}"

def get_git_commit_date():
    try:
        return subprocess.check_output(['git', 'log', '-1', '--date=format:%Y%m%d', '--format=%ad']).decode('ascii').strip()
    except Exception as e:
        return f"Could not get gith version: {e}"
