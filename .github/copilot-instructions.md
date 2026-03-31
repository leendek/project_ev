# Copilot Context Definition: Intelligent EV Mobility Assistant

## Project Intent
Build a generative AI assistant for weekly EV mobility and charging planning.
The assistant should reason across multiple days, interact naturally with users, and produce structured outputs that can be consumed by downstream energy optimization systems.

## Primary Goals
- Manage and update calendar events through natural conversation.
- Ask clarifying questions when time, location, or constraints are missing.
- Estimate travel time and distance.
- Learn recurring mobility patterns from historical behavior.
- Predict multi-day vehicle usage and charging needs.
- Identify feasible charging windows under time and energy constraints.
- Generate machine-consumable JSON schedules of car availability.

## Domain Constraints
- Plans must consider time, location, and battery/energy constraints jointly.
- Agenda information can be incomplete, ambiguous, or dynamic.
- Recommendations should be transparent and editable by user feedback.
- Outputs should preserve a clear separation between assumptions and confirmed facts.

## System Components to Assume
- Chat-first user interface (voice optional).
- LLM agent orchestrating tools and dialogue.
- Tooling for:
  - Calendar read/write
  - Travel estimation
  - Charging estimation
  - Structured JSON generation
- Memory/RAG layer with:
  - Past trips and user habits
  - Vehicle configuration (battery, consumption, charging time)
- Planning module for multi-day constrained reasoning.

## Copilot Behavior Requirements
When helping in this repository, prioritize:
- Agent-based tool orchestration over single-step answers.
- Multi-step planning for weekly schedules.
- Clarification prompts before committing uncertain assumptions.
- Structured outputs that can be validated against schemas.
- Practical implementation details for RAG, planning, and evaluation.

## Output Contract
Default to generating JSON compatible with availability scheduling and optimization pipelines.
Use a format similar to:

```json
{
  "date": "2026-04-02",
  "car_availability": [
    {"start": "00:00", "end": "08:30"},
    {"start": "18:00", "end": "23:59"}
  ]
}
```

## Evaluation Focus
Prioritize code and design decisions that improve:
- Functional accuracy (travel and charging estimates)
- Robustness in scenario simulations (missed charging, corrections)
- Measurable impact of RAG and agent reasoning (ablation-friendly design)
- Interaction quality (clarity, usefulness, and corrective loops)

## Non-Goals (for now)
- Building a full production voice stack.
- Over-optimizing UI before planning and data contracts are stable.

## Coding Guidance
- Keep planning logic modular and testable.
- Keep tool interfaces explicit and typed where possible.
- Keep schemas versioned for downstream optimizer compatibility.
- Prefer deterministic transformations before LLM post-processing when possible.
