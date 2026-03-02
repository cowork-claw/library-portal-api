# External Blind Review Session

Session id: ext_20260302_060506_f28085f2
Session token: 75a4378c5d13ea6fb108e56655f8cd39
Blind packet: /app/.desloppify/review_packet_blind.json
Template output: /app/.desloppify/external_review_sessions/ext_20260302_060506_f28085f2/review_result.template.json
Claude launch prompt: /app/.desloppify/external_review_sessions/ext_20260302_060506_f28085f2/claude_launch_prompt.md
Expected reviewer output: /app/.desloppify/external_review_sessions/ext_20260302_060506_f28085f2/review_result.json

Happy path:
1. Open the Claude launch prompt file and paste it into a context-isolated subagent task.
2. Reviewer writes JSON output to the expected reviewer output path.
3. Submit with the printed --external-submit command.

Reviewer output requirements:
1. Return JSON with top-level keys: session, assessments, findings.
2. session.id must be `ext_20260302_060506_f28085f2`.
3. session.token must be `75a4378c5d13ea6fb108e56655f8cd39`.
4. Include findings with required schema fields (dimension/identifier/summary/related_files/evidence/suggestion/confidence).
5. Use the blind packet only (no score targets or prior context).
