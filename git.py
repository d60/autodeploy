import subprocess


def clone(repo: str, directory: str):
    subprocess.run([
        'git',
        'clone',
        repo,
        directory
    ])


def pull(directory: str):
    subprocess.run([
        'git',
        '-C', directory,
        'pull'
    ])
