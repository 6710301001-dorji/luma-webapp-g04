# Queue response benchmark

## Scope

This report measures the user-visible response change introduced by the backend
job queue. It compares the synchronous AI-engine request path with the queued
backend path using the same mock Forge configured with a fixed 10-second delay.
The run used three independent batches of five simultaneous jobs per path.

The SQLite database was created through the Alembic migration chain. The queued
path used normal registration, login, CSRF protection, `POST /api/generate`, and
polling through `GET /api/jobs/<id>` until every job reached `done`.

## Results

| Measurement | Samples | p50 | p95 |
|---|---:|---:|---:|
| Synchronous `POST /forge/txt2img` response | 15 | 10.036 s | 10.090 s |
| Queued `POST /api/generate` HTTP 202 | 15 | 0.0169 s | 0.0219 s |
| `GET /api/jobs/<id>` status poll | 1,667 | 0.00543 s | 0.00985 s |
| Queued time until job completion | 15 | 30.237 s | 50.323 s |

The median queued submission response was about **595× faster** than waiting for
the synchronous image response. This result shows that the queue removes the
long wait from the HTTP submission request. It does not make image generation
itself faster: one worker still processes the five jobs sequentially, so the
fifth completion in a batch occurs at about 50 seconds.

Raw trials are in `queue_comparison_raw.csv`; exact summary values are in
`queue_comparison_summary.csv`; environment and workload details are in
`queue_comparison_metadata.json`.

## Filter timing

On the same machine, a 15×15 direct 2D box convolution took 13.283 ms median and
the equivalent separable implementation took 0.816 ms median, a **16.28× measured
speedup**. The maximum output difference was 0.0000763, confirming numerical
equivalence within floating-point precision.

## Remaining measurement

The required graph of generation time versus diffusion `steps` still needs a
reachable real Forge/GPU model. Mock Forge applies a fixed delay independent of
`steps`, so using it for that graph would not measure the required relationship.
Run the benchmark with `--measure-real-steps` when Forge is available and record
the model, sampler, scheduler, and GPU beside the result.
