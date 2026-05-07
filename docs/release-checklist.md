# NxJob Release Checklist

Before every release:

- README is current.
- LICENSE exists and matches the intended distribution model.
- Version is updated.
- Git tag is created.
- Release notes describe user-facing changes and known limits.
- Windows local-service installer is generated.
- Browser extension package is generated.
- `release-manifest.json` is generated.
- `docs/install-windows.md` is current.
- `docs/release-test-record.md` is copied or filled for this release.
- Installer test result is recorded.
- Version differences from the previous release are recorded.
- Desktop/local-service data source and browser-extension data source boundaries are clear.

MVP should present installers and packaged artifacts to non-technical users, not source code or development scripts.

