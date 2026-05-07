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
2. Double-click:

```text
Install NxJob Local Service.bat
```

3. Double-click:

```text
Start NxJob Local Service.bat
```

4. Double-click:

```text
Check NxJob Local Service.bat
```

Expected result:

```json
{
  "status": "ok",
  "service": "nxjob-local-service"
}
```

5. To check service status later, double-click:

```text
Status NxJob Local Service.bat
```

6. To stop the service, double-click:

```text
Stop NxJob Local Service.bat
```

## Command-Line Alternative

Open PowerShell in the extracted folder and run:

```powershell
.\scripts\install-local-service.ps1
```

4. Start the service:

```powershell
.\scripts\start-local-service.ps1 -Background
```

Check health:

```powershell
.\scripts\check-health.ps1
```

```powershell
.\scripts\status-local-service.ps1
```

```powershell
.\scripts\stop-local-service.ps1
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

Run:

```text
Uninstall NxJob Local Service.bat
```

Command-line alternative:

```powershell
.\scripts\uninstall-local-service.ps1
```

Remove the unpacked browser extension from the browser extension page.
