# AppWorld static API inventory result

The one-shot remote inventory passed safely at revision
`ae0d3ec6b8e8f32ab9b451665230a97806943540`. Its SHA-256 is
`626087bf090c7eb9b279445888d0b248a0408cf0fe534843233e0281a9f0faf2`.

All 72 Python/stub members parsed into a complete syntactic callable superset
of 1,035 candidates. The frozen effect counts are 376 `read_only`, zero
`idempotent_state_setting`, zero `non_idempotent_side_effect`, and 659
`unknown_effect`. Consequently `full_effect_coverage=false`.

The run itself passed every safety check. It persisted only hashes and standard
evidence codes, extracted no source, imported no protected module, accessed no
tests/data/tasks, and used no model or GPU.

The capacity gate failed under the frozen conservative proof rules. This does
not show that AppWorld lacks state-changing APIs, and it does not assess the
PROPER method; it shows that this static, scenario-independent evidence method
cannot establish the required effect coverage. The result cannot be rerun or
used for post-result rule tuning. No targets may be selected, and the AppWorld
qualification route stops here.
