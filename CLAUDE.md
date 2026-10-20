# raddai-backend (main portal API)

Django REST API for Laazeere Academy, deployed on cPanel (MySQL). Frontend is the raddai-lms repo; the exam portal (laazeere-exams) pushes scores to it.

## Deploy
- User runs `git pull origin master`, then `python manage.py migrate` only if there is a migration, then Restart in cPanel.
- Default branch: `master`. Work on the assigned branch, never push elsewhere.

## Run and test locally
- `.venv` runs on SQLite (no mysqlclient): `.venv/bin/python manage.py test core`.
- 6 AdmissionFlow/AdmissionManagement tests already fail on master. Ignore them, mention if relevant.

## Things to know
- Result: `marks_obtained = ca1+ca2+ca3+exam`, total 100. Pre-Nursery to Nursery 2 (grade < 1) use CA1/20, CA2/20, no CA3, Exam/60; every other class 10/10/10/70 (`score_limits_for_grade`). The exam-portal endpoint `record_exam_result` keeps 10/10/10/70.
- Deleting a Student cascades to Results, FeePayments and Attendance. The login User is not deleted. Delete needs `?confirm=<student_id>` and management/admin.
- Fee lookup: `_resolve_tuition_fee` (grade, section, gender, department, student type).

## How to work with me
- Short, plain answers. No long recaps.
- Test before reporting (run the tests; for UI changes check it in a browser). Say plainly if something failed or was skipped.
- Never merge until I say "merge". Then create the PR, merge it, check the deploy is READY and report in a line or two.
- Say whether a change is frontend-only, needs a migration, or needs a cPanel pull + Restart.
- Do not touch the other portal when a change is for one portal only.
- Never decrypt Vercel env values. No destructive Neon/database actions without asking first.
- Commit trailer: `Co-Authored-By: Claude <noreply@anthropic.com>`.
- Keep token use low: read only the files needed, no huge outputs, screenshots only for UI changes.

