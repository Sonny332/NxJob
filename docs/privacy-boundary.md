# Privacy Boundary

NxJob is local-first. Private job search data must stay on the user's machine by default.

## Never Commit

Do not commit these files or directories:

- `private/`
- Real master resume files.
- Generated tailored resumes.
- Local SQLite databases.
- Prompt logs containing private resume or job application content.
- Real application records, recruiter replies, or interview notes.

## Repository-Safe Content

The repository may contain:

- Schema definitions.
- Parser and renderer code.
- Synthetic fixtures.
- Documentation.
- Tests using fake resume and job data.

## MVP Rule

During MVP development, a real master resume may be used only as a local private file. The local service can read it through `NXJOB_MASTER_RESUME_PATH`, but the file must not be staged, committed, or uploaded to GitHub.

Current local MVP setup may place the user's real master resume at `private/master-resume/`. This directory is intentionally ignored by Git.

## Future Direction

NxJob should later provide a helper skill or UI flow that converts a normal resume into the structured master resume format. That generated file still belongs to local private storage unless the user explicitly exports it.
