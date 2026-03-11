# Git + GitHub CI Workflow

## 1. Making changes locally

```bash
# Check what files you've changed
git status

# See the actual diff of changes
git diff
```

## 2. Staging files for commit

```bash
# Stage specific files (preferred — avoids accidentally committing secrets)
git add build_files/build.sh system_files/etc/skel/.config/hypr/autostart.conf

# Or stage everything (use with caution)
git add -A
```

Staging = marking files to be included in the next commit. Think of it as a "ready to save" list.

## 3. Committing

```bash
git commit -m "fix: correct SwayOSD COPR name to lowercase"
```

A commit is a snapshot of your staged changes with a message explaining what you did. It's saved **locally only** — GitHub doesn't know about it yet.

## 4. Pushing to GitHub

```bash
git push
```

This uploads your local commits to the remote repository on GitHub. This is when CI kicks in.

## 5. What happens on GitHub (CI)

Your repo has `.github/workflows/build.yml`. Every time you push to `main`, GitHub Actions:

1. Spins up a fresh Ubuntu VM
2. Checks out your code
3. Runs `buildah build` using your `Containerfile`
4. If the build succeeds, pushes the image to `ghcr.io/LuisUma92/omyfendory:latest`
5. Signs it with cosign

You don't run any of this — it's automatic on push.

## 6. Monitoring CI

```bash
# List recent workflow runs
gh run list --limit 5

# Watch a running build in real-time
gh run watch

# View logs of a specific run
gh run view <run-id> --log

# View only the failed step's logs
gh run view <run-id> --log-failed
```

## 7. Checking for errors (what we've been doing)

```bash
# Quick way to find errors in a failed build
gh run view <run-id> --log-failed 2>&1 | grep -E "(No match|not found|Error|Failed)" | head -20
```

### Typical fix cycle

```bash
# 1. Find the error
gh run view <run-id> --log-failed

# 2. Edit the file to fix it
nano build_files/build.sh

# 3. Stage, commit, push
git add build_files/build.sh
git commit -m "fix: description of what you fixed"
git push

# 4. Watch the new build
gh run watch
```

### The pending fix right now

The COPR name is case-sensitive. In `build_files/build.sh`, change `erikreider/SwayOSD` to `erikreider/swayosd` (lowercase) in both the enable and disable lines (lines 16 and 91). Then stage, commit, and push.
