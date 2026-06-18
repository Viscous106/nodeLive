<!-- Keep PRs small and focused. One feature slice per PR. -->

## What & why

<!-- What does this change do, and why is it needed? Link the relevant doc/checklist. -->

## Branch / scope

- [ ] Dashboard (`feat/dashboard`) · [ ] Live meeting (`feat/live-meeting`) · [ ] Shared/foundation
- Plan reference: <!-- e.g. docs/branch-A-dashboard.md Day 1 -->

## Shared-contract impact

<!-- Does this change anything Dev A and Dev B both depend on?
     (User/ClassSession models, Pydantic/TS shapes, socket events, API routes) -->
- [ ] No shared-contract change
- [ ] Changes a shared contract — described above and the other dev is aware

## Checklist

- [ ] `ruff check . && ruff format --check .` passes (backend)
- [ ] `pytest` passes (backend)
- [ ] `npm run build` passes (frontend)
- [ ] New logic has tests
- [ ] No secrets / `.env` committed
- [ ] Commits are signed under my own identity
