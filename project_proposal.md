# Project Proposal: Intelligent EV Mobility Assistant using Generative AI

## Problem Definition

The adoption of electric vehicles (EVs) introduces new challenges in managing mobility, scheduling, and charging constraints. Users must coordinate:
· Time-dependent travel patterns
· Battery usage and charging needs
· Dynamic and incomplete agendas

Current tools (calendar/navigation) lack multi-day reasoning and do not integrate user interaction with energy-aware planning.

👉 This project aims to develop an AI-powered assistant that supports weekly mobility and EV charging planning through natural interaction. The output of the assistant can be used in energy optimizers like linear programming to decide when, with how much power and with which tool (grid, solar, storage battery) the car will be charged.

## Proposed Solution

We propose an agent-based AI assistant (chat-first, optional voice) that:
· Manages and updates the user’s calendar
· Asks clarifying questions when information is missing
· Estimates travel time and distance
· Learn from the past and propose to the user the most probable schedule
· Predicts multi-day vehicle usage
· Determines optimal EV charging windows
· Outputs structured JSON schedules of car availability
· Updates the agenda via natural conversation

## System Architecture

A modular AI pipeline with an LLM agent at its core:
· User Interface: Chat (text), optional voice
· LLM Agent: Controls interaction, tool use, and context
· Tools:
    o Calendar (read/write)
    o Travel estimation
    o Charging estimator
    o JSON generator
· Memory (RAG):
    o Stores past trips and user habits
    o Includes vehicle configuration (battery, consumption, charging time)
· Planning Module:
    o Multi-day reasoning under constraints (time, location, energy)
    o Detects charging needs and available time slots

## Key AI Techniques

· Agent-based reasoning (LLM + tool use)
· Retrieval-Augmented Generation (RAG)
· Structured output generation (JSON schema)
· Multi-step planning and reasoning
· (Optional) Multimodal interaction (voice)

## Data Pipeline

· Inputs: Calendar data, travel data (API/synthetic), user history
· Processing:
    o Normalize events
    o Extract time/location
    o Store structured trip history for retrieval

## Evaluation

· Functional accuracy: travel estimates, charging predictions, time slots
· Scenario testing: simulate weekly schedules (errors, missed charging, corrections)
· Ablation study: compare with/without RAG and agent reasoning
· User interaction quality: clarity and usefulness

## Expected Output

· Working prototype (chat assistant)
· Automated calendar updates
· Daily JSON availability schedules:

{ "date": "2026-04-02", "car_availability": [ {"start": "00:00", "end": "08:30"}, {"start": "18:00", "end": "23:59"} ] }

## Innovation

· Combines mobility, scheduling, and energy planning
· Performs multi-day reasoning under constraints
· Uses agent-based AI with structured outputs
· Enables proactive interaction, not just reactive responses
