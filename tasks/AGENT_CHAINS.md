# Agent-chain suite — multi-turn tool pipelines (6 tasks)

Real subagent work is 3-6 sequential tool calls where each call depends on the
previous result. These tasks test sustained multi-turn coherence: reading tool
outputs, carrying values forward, and finishing the whole chain.

- **chain_flight_booking**: search flights → pick cheapest → reserve it → report confirmation number.
- **chain_file_pipeline**: write_file → append twice → read back → verify content.
- **chain_lookup_transform**: look up a record → transform a field (tier multiplier) → write result.
- **chain_error_midway**: a mid-chain tool call fails once → model must recover and complete the chain.
- **chain_conditional**: tool output determines a branch (if price > 100 use discount code, else don't).
- **chain_parallel_merge**: two independent lookups → merge results into one summary.

Each is scored by final sandbox state (was the right thing actually done in the
right order?) plus the final text containing the required artifacts
(confirmation number, file content, computed value).
