# Team Git Runbook

Remote: https://github.com/Hesara2003/Innovatex.git

## Initial setup (PowerShell)
```powershell
# From project root
git remote add origin https://github.com/Hesara2003/Innovatex.git
# If remote exists, update it
# git remote set-url origin https://github.com/Hesara2003/Innovatex.git

# Push main and team branches
git push -u origin main
git push -u origin dilusha
git push -u origin hesara
git push -u origin sandil
git push -u origin sandali
```

## Daily workflow
```powershell
# Sync latest main
git checkout main
git pull --ff-only origin main

# Switch to your branch
git checkout <your-branch>
# Or create a task branch off yours
git checkout -b <your-name>/<task-slug>

# Stage and commit small, focused changes
git add -A
git commit -m "feat: short description"

# Push and open a PR to main
git push -u origin HEAD
# Then open PR in GitHub UI; request a teammate review
```

## Conventions
- Keep `evidence/executables/run_demo.py` runnable at all times.
- Use `# @algorithm Name | Purpose` in relevant source files.
- Prefer fast-forward merges; rebase your branch before merging to main.

## Troubleshooting
- Remote already exists: use `git remote set-url origin <url>`.
- Diverged branches: `git pull --rebase` on your branch before pushing.
- Line endings: Windows may convert LF to CRLF locally; repository uses LF.
