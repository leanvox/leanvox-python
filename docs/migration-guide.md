# Migration Guide

> Template for future version migrations. Update this as breaking changes are introduced.

---

## v0.1.x → v0.2.x

_No migrations yet — this is the first release._

### Template for Future Entries

```markdown
## vX.Y → vX.Z

### Breaking Changes
- **`method_name()` renamed to `new_name()`** — Update all calls.
- **`param` removed** — Use `new_param` instead.

### New Features
- Added `new_method()` for X.

### Migration Steps
1. Update import: `from leanvox import NewThing`
2. Replace `old_call()` with `new_call()`
3. Run tests to verify.

### Deprecations
- `old_method()` deprecated, will be removed in vX.Z+1.
```

---

*Keep this guide updated with every release that includes breaking changes.*
