# PROPER v2.3 outputs

Generated v2.3 artifacts belong in versioned subdirectories here. They are
ignored by default and may be force-added only by exact, audited result
directory after a stage completes.

Never copy or regenerate frozen v2.x results into this namespace.

The first local stage writes only CPU/scripted validation to
`first_stage_validation/results.json`. That artifact is not model evidence and
does not authorize a GPU run.
