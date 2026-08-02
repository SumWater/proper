# Native tau3 branch replay smoke result

The one-shot remote CPU smoke passed at remote project revision
`bcc758badf692932008824d0d0d05fcda865a177` against pinned tau3 revision
`fc0055dc4e0a316c3f83133267fbd6faaa770992`.

The isolated retail fixture dynamically selected one pending order, executed
`cancel_pending_order` exactly once, captured the complete post-action database
checkpoint, and restored it into a second fresh environment. All nine native
checks passed. The restored order remained cancelled, environment mutation
replay was empty, and checkpoint SHA-256 matched exactly before and after
restoration:

`ef6888f24cb08db72f80d8a4d47c3ae9c530452d05fef760d61a77383c1a4d40`

The returned result SHA-256 is:

`ef8fac9162e28af8ea0b9f552b370ffffb9d9289482eef40be604d9885166a14`

No benchmark task, model, model output, or GPU was used. The result validates
the native split-state replay mechanism only. It authorizes freezing a real
public branch capture protocol, but not executing the 12 development targets,
freezing a model protocol, implementing a model runner, running a model/GPU, or
making held-out or confirmatory claims.
