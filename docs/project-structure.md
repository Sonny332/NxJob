# NxJob Project Structure

## Target Structure

```text
NxJob/
  README.md
  LICENSE
  AGENTS.md
  docs/
    product-blueprint.md
    tech-stack.md
    project-structure.md
    data-model.md
    api-schema.md
    mvp-scope.md
    design.md
    release-checklist.md
  apps/
    extension/
      package.json
      wxt.config.ts
      entrypoints/
        popup/
        content.ts
        background.ts
      src/
        components/
        lib/
          api-client.ts
          page-capture.ts
          form-context.ts
        styles/
      tests/
    local-service/
      pyproject.toml
      src/
        nxjob/
          main.py
          api/
          core/
            platform.py
          db/
          models/
          schemas/
          workflows/
            sponsorship_analyzer.py
            resume_tailor.py
            form_answer_drafter.py
          ai/
          resumes/
            document_validation.py
          forms/
          storage/
            paths.py
          settings/
      tests/
        unit/
        api/
        fixtures/
      templates/
        resume/
  packages/
    shared/
      schemas/
        api.schema.json
      src/
        types.ts
  data/
    samples/
      jd/
      resumes/
      forms/
  scripts/
    dev/
    build/
    package/
    release/
  installers/
  releases/
```

## Ownership

- `apps/extension`: user layer, browser UI, content extraction, field fill confirmation.
- `apps/local-service`: local runtime layer, workflows, persistence, rendering, AI orchestration.
- `packages/shared`: schema source shared by extension and service.
- `docs`: source of truth for product, technical decisions, release rules.
- `data/samples`: non-sensitive fixtures for local tests and smoke checks.
- `installers` and `releases`: generated artifacts only. Do not expose these as the developer entry point in README.

## M1 Creation Order

1. Create root project metadata: `README.md`, `LICENSE`, `AGENTS.md`.
2. Create `apps/local-service` with `GET /health`.
3. Create `apps/extension` with WXT popup or side panel.
4. Create `packages/shared/schemas/api.schema.json`.
5. Add scripts for local dev startup.
6. Add smoke tests for local service health and extension build.

## Public User Entry

README should default to installation-package usage for non-technical users.

Developer setup can exist, but it must be clearly separated under a developer section and not be the first path shown.

## Release Checklist Requirement

Before any release, verify:

- README is current.
- LICENSE exists.
- Version/tag is updated.
- Release notes exist.
- Installer and extension package exist.
- Packaging test result is recorded.
- Version differences are recorded.
