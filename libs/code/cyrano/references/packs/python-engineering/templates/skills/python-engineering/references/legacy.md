# Legacy repositories

Do not repair thousands of unrelated violations during a feature change.
Use the approved immutable baseline. Preserve the full raw diagnostics.
Changed files must be clean as whole files unless an explicit scoped
exception is approved. Only byte-identical unchanged files may use the
v1 diagnostic baseline, with the same policy and toolchain.

Equal diagnostic counts do not imply equal diagnostics. New findings fail.
A stale baseline must be reviewed, not silently regenerated. Test failures
are not baseline-covered in v1. PASS_WITH_BASELINE is not debt-free PASS.
