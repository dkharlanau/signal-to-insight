# 15-minute external usability test

This kit measures whether a first-time user can understand and verify the released public proof path. It does not process a new source, publish review content, or claim a human learning outcome.

## Participant and privacy boundary

Suitable participant: a researcher, analyst, knowledge-management practitioner, technical learner, or research-agent builder unfamiliar with Signal to Insight.

Use only the published golden walkthrough. Do not submit private reading history, unpublished notes, full third-party text, personal profile data, or confidential source material.

## Facilitator script

| Time | Participant task | Observe without coaching |
| --- | --- | --- |
| 0–2 min | Read the first README screen and explain why this is not a generic summarizer. | Incorrect product expectations. |
| 2–5 min | Open the golden walkthrough and locate source provenance, the whole-source model, and Knowledge Delta. | Navigation and terminology friction. |
| 5–8 min | Identify one source claim and one project interpretation. | Whether evidence origins remain distinct. |
| 8–11 min | Find the Source Decision and explain whether the original source is still needed. | Whether the decision is supported rather than decorative. |
| 11–13 min | Inspect the delayed-reconstruction checkpoint. | Whether “pending” is understood as missing human evidence. |
| 13–15 min | Run the validation command from the [golden quickstart](GOLDEN_QUICKSTART_RELEASE.md) or explain what it verifies. | Confusion between contract validation and learning success. |

Stop if repository setup consumes more than six minutes. Record the blocker rather than completing the task for the participant.

## Blank result record

```text
Release/tag tested:
Operating system and Python version:
Participant role (no employer/client name):
Completed within 15 minutes: yes / no
First blocker:
Source claim vs project interpretation distinguished: yes / no
Source Decision understood: yes / no / unclear
Pending human checkpoint understood: yes / no / unclear
Validation-vs-learning boundary understood: yes / no / unclear
Most useful part:
Most confusing term or step:
Suggested improvement:
```

Submit privacy-safe results through the [external usability feedback form](https://github.com/dkharlanau/signal-to-insight/issues/new?template=usability-feedback.yml). Planned sessions, maintainer walkthroughs, CI, and empty forms are not external adoption evidence.
