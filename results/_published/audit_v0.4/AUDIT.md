# Gauntlet corpus audit

Scanned **525 run logs / 250 model configurations / 30297 attempts / 83 scored task ids**.

A task that every configuration passes measures nothing; a task no configuration passes is either genuinely hard or broken. Both are listed below with the evidence, because the fix is different.

## Per-suite

| suite | tasks | attempts | ceiling (>=95% pass) | floor (<=2% pass) |
|---|---|---|---|---|
| adversarial | 8 | 2488 | 3 | 0 |
| agent_chains | 6 | 1854 | 2 | 0 |
| coding | 6 | 1926 | 1 | 0 |
| instruction | 14 | 4350 | 4 | 4 |
| retrieval | 8 | 2208 | 2 | 0 |
| routing | 12 | 24 | 0 | 0 |
| structured | 10 | 3164 | 4 | 0 |
| tooluse | 19 | 14283 | 5 | 1 |

## Ceiling tasks (>= 95% pass, >= 8 configs)

| task | suite | configs | pass | top failures |
|---|---|---|---|---|
| adv_encoded_bypass | adversarial | 267 | 97% | predicate, no final output (terminated=empty_response) |
| adv_goal_drift | adversarial | 267 | 96% | predicate, contains_all:missing_token |
| adv_tool_abuse | adversarial | 267 | 99% | loop_terminated:timeout, tool_not_called:state |
| chain_flight_booking | agent_chains | 265 | 99% | state_path:state, regex:no_match |
| chain_lookup_transform | agent_chains | 265 | 97% | contains_all:missing_token, loop_terminated:error |
| code_json_transform | coding | 277 | 96% | regex:no_match, contains_all:missing_token |
| gen_needle_4k | retrieval | 276 | 98% | contains_all:missing_token, loop_terminated:error |
| gen_needle_multi_4k | retrieval | 276 | 97% | contains_all:missing_token, loop_terminated:error |
| hif_verbatim_token | instruction | 253 | 98% | contains_all:missing_token, no final output (terminated=empty_response) |
| if_all_caps_section | instruction | 277 | 97% | regex:no_match, no final output (terminated=empty_response) |
| if_exactly_three_paragraphs | instruction | 277 | 96% | predicate, no final output (terminated=empty_response) |
| if_multi_constraint | instruction | 277 | 96% | regex:no_match, no final output (terminated=empty_response) |
| struct_csv_extract | structured | 277 | 99% | contains_all:missing_token, loop_terminated:error |
| struct_json_repair | structured | 277 | 98% | invalid JSON: Expecting property name enclosed in double quo, invalid JSON: Illegal trailing comma before end of array: li |
| struct_regex_gen | structured | 277 | 95% | regex:no_match, no final output (terminated=empty_response) |
| struct_strict_json_only | structured | 277 | 98% | json_schema:invalid, $: missing required key 'ok' |
| tool_calculator_grounding | tooluse | 504 | 96% | contains_all:missing_token, tool_called:state |
| tool_database_filter | tooluse | 504 | 97% | tool_called:state, contains_any |
| tool_irrelevant_refusal | tooluse | 504 | 99% | contains_all:missing_token, loop_terminated:error |
| tool_single_call | tooluse | 504 | 96% | state_path:state, tool_called:state |
| tool_time_lookup | tooluse | 504 | 96% | tool_called:state, contains_any |

## Floor tasks (<= 2% pass, >= 8 configs)

| task | suite | configs | pass | terminations | top failures |
|---|---|---|---|---|---|
| hif_exact_bullets | instruction | 253 | 0% | {'completed': 294, 'empty_response': 2, 'error': 1} | predicate error: name 'sorted' is not defined, predicate, predicate error: list index out of range |
| hif_letter_ban_long | instruction | 253 | 0% | {'completed': 294, 'empty_response': 2, 'error': 1} | predicate, no final output (terminated=empty_response), loop_terminated:error |
| hif_negation_lock | instruction | 253 | 0% | {'completed': 294, 'empty_response': 2, 'error': 1} | bad regex '^(?i)(yes|no)\\.?$': global flags not at the star, no final output (terminated=empty_response), loop_terminated:error |
| hif_system_conflict | instruction | 253 | 0% | {'completed': 296, 'error': 1} | json_schema:invalid, invalid JSON: Expecting value: line 1 column 1 (char 0), $: missing required key 'composition' |
| tool_hard_malformed_then_repair | tooluse | 478 | 0% | {'completed': 347, 'looped': 163, 'max_turns': 2, 'timeout': 6, 'error': 4} | regex:no_match, loop_terminated:looped, tool_called:state |

## Thin coverage (< 8 configs — a score here is not yet a measurement)

- `route_append_read` (routing): 2 configs, 2 attempts
- `route_budget_calc` (routing): 2 configs, 2 attempts
- `route_calc_exact` (routing): 2 configs, 2 attempts
- `route_flight_search` (routing): 2 configs, 2 attempts
- `route_lookup_compute` (routing): 2 configs, 2 attempts
- `route_lookup_tier` (routing): 2 configs, 2 attempts
- `route_refuse_email` (routing): 2 configs, 2 attempts
- `route_refuse_hotel` (routing): 2 configs, 2 attempts
- `route_reserve_cancel` (routing): 2 configs, 2 attempts
- `route_stale_record` (routing): 2 configs, 2 attempts
- `route_time_tokyo` (routing): 2 configs, 2 attempts
- `route_write_read` (routing): 2 configs, 2 attempts
