# NxJob Windows Install

NxJob MVP ships as two artifacts:

- `nxjob-local-service-<version>.zip`
- `nxjob-extension-<version>.zip`

## Install Local Service

Prerequisites:

- Windows PowerShell.
- Python 3.11 or newer available as `python`.
- Network access for Python dependency installation unless dependencies are already cached.

1. Extract `nxjob-local-service-<version>.zip`.
2. Open PowerShell in the extracted folder.
3. Run:

```powershell
.\scripts\install-local-service.ps1
```

4. Start the service:

```powershell
.\scripts\start-local-service.ps1
```

5. Check health:

```powershell
.\scripts\check-health.ps1
```

Expected result:

```json
{
  "status": "ok",
  "service": "nxjob-local-service"
}
```

## Configure Private Master Resume

Create a local master resume JSON file following `docs/master-resume-format.md`.

Set this environment variable before starting the service:

```powershell
$env:NXJOB_MASTER_RESUME_PATH = "C:\path\to\private\master_resume.json"
```

Do not place real resume content in Git-tracked folders.

## Install Browser Extension

1. Extract `nxjob-extension-<version>.zip`.
2. Open a Chromium browser extension page.
3. Enable developer mode.
4. Load the extracted extension folder.

## Runtime Boundary

- The extension reads selected page text and focused form fields only after user action.
- The local service stores data locally in SQLite.
- NxJob never clicks submit, bypasses verification, or bulk-applies.
- Generated resumes and private master resume files stay local.

## Uninstall

Remove the local service folder:

```powershell
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\NxJob\LocalService"
```

Remove the unpacked browser extension from the browser extension page.
