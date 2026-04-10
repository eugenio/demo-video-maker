# Prompt Examples for Scenario Generation

> Use these prompts with an LLM to generate YAML scenario files for demo-video-maker.

---

## Base Prompt Template

Use this as the system prompt when asking an LLM to generate scenarios:

```
You are a demo video scriptwriter for demo-video-maker, a tool that records
browser interactions and produces narrated MP4 videos from YAML scenario files.

Generate a YAML scenario file following this schema:

title: string (demo title)
base_url: string (root URL, default http://localhost:8080)
resolution: [width, height] (default [1920, 1080])
pause_between_steps: float (seconds between frames, default 2.0)
voice: string (TTS voice, default "onyx")

steps: list of actions:
  - action: navigate|click|type|scroll|hover|wait|screenshot
    url: string (for navigate)
    selector: string (CSS selector for click/type/hover/scroll)
    text: string (for type action)
    distance: int (pixels for scroll)
    narration: string (spoken text, 10-30 words per step)
    highlight: string (CSS selector to outline in blue)
    wait_for: string (CSS selector to wait for before screenshot)
    wait_seconds: float (for wait action)
    duration_override: float (override default pause)

Rules for narration:
- 10-30 words per step (3-8 seconds of audio)
- Describe WHAT the user sees and WHY it matters
- Action-oriented: reference the element being interacted with
- Avoid jargon unless the audience is technical
- Each step builds on the previous one narratively
```

---

## Prompt 1: Feature Walkthrough

```
Generate a YAML scenario for demo-video-maker that walks through
the [FEATURE NAME] feature of my web app at [URL].

The demo should:
- Start at the main page and navigate to the feature
- Show 5-7 key interactions (clicks, form fills, results)
- Include narration explaining each step to a first-time user
- Highlight important UI elements with the highlight field
- Use wait_for on navigation steps to ensure pages load

Target audience: [product managers / developers / end users]
Tone: [professional / casual / technical]
```

**Example filled in:**

```
Generate a YAML scenario for demo-video-maker that walks through
the project management feature of my web app at http://localhost:3000.

The demo should:
- Start at the dashboard and navigate to the projects page
- Show creating a new project, adding tasks, assigning team members
- Include narration explaining each step to a first-time user
- Highlight the key action buttons with the highlight field
- Use wait_for on navigation steps to ensure pages load

Target audience: product managers
Tone: professional
```

---

## Prompt 2: Bug Reproduction

```
Generate a YAML scenario for demo-video-maker that reproduces
a bug I found in my web app.

App URL: [URL]
Bug: [description of the bug]
Steps to reproduce:
1. [step 1]
2. [step 2]
3. [step 3]

The narration should:
- Explain what the expected behavior is at each step
- Point out where the actual behavior diverges
- Keep a neutral, factual tone suitable for a bug report
```

---

## Prompt 3: Before/After Comparison

```
Generate TWO YAML scenario files for demo-video-maker:

1. "before.yaml" -- shows the current UX flow (slow, confusing, broken)
2. "after.yaml" -- shows the improved UX flow

App URL: [URL]
Feature being improved: [description]
Key improvements:
- [improvement 1]
- [improvement 2]
- [improvement 3]

The narration should contrast the old and new experience.
Use the same steps in both files so the comparison is direct.
```

---

## Prompt 4: API Demo

```
Generate a YAML scenario for demo-video-maker that demonstrates
my API using the Swagger/OpenAPI docs UI.

API docs URL: [URL]/docs
Endpoints to demonstrate:
1. [endpoint 1 with description]
2. [endpoint 2 with description]

The demo should:
- Navigate to the API docs page
- Expand each endpoint section
- Use "Try it out" to send requests
- Show the response
- Narrate what each endpoint does and when to use it
```

---

## Prompt 5: Onboarding Tutorial

```
Generate a YAML scenario for demo-video-maker that serves as
a new user onboarding tutorial for my web app.

App URL: [URL]
Key features to cover (in order of importance):
1. [feature 1]
2. [feature 2]
3. [feature 3]
4. [feature 4]

The demo should:
- Start at the landing page
- Walk through registration/login if applicable
- Visit each feature area with 1-2 interactions each
- End with a summary view (dashboard or home)
- Keep narration friendly and encouraging
- Total: 8-12 steps, under 60 seconds of narration
```

---

## Prompt 6: Multi-Language Demo

```
Generate a YAML scenario for demo-video-maker in [LANGUAGE].

App URL: [URL]
Feature: [description]

Requirements:
- All narration text must be in [LANGUAGE]
- Use natural, conversational phrasing (not machine-translated)
- Keep narration at 10-25 words per step
- The app UI may be in English; narration explains what is shown

Target TTS voice: [voice name, e.g., if_sara for Italian]
```

---

## Prompt 7: Release Notes Video

```
Generate a YAML scenario for demo-video-maker that showcases
the new features in version [X.Y.Z] of my web app.

App URL: [URL]
New features:
1. [feature + location in the app]
2. [feature + location in the app]
3. [feature + location in the app]

Bug fixes to show:
1. [fix + how to verify it works]

The narration should:
- Open with a brief version announcement
- Show each new feature with 1-2 interactions
- Close with a summary of what changed
- Tone: excited but professional
- Total: 6-10 steps
```

---

## Narration Writing Tips

### Length Guide

| Words | Duration | Use for                          |
|-------|----------|----------------------------------|
| 5-10  | 2-3s     | Simple click or navigation       |
| 10-20 | 4-6s     | Feature explanation              |
| 20-30 | 7-10s    | Complex workflow step            |
| 30+   | 10s+     | Avoid -- split into two steps    |

### Good Narration Patterns

```yaml
# Feature introduction (what + why)
narration: "The dashboard gives you a real-time overview of all active jobs, with status indicators and estimated completion times."

# Action + outcome
narration: "Click the filter button to narrow results by date, priority, or status."

# Highlight discovery
narration: "Notice the confidence score on each card. Green indicates high reliability."

# Transition
narration: "Now let's look at how the comparison tool works."

# Summary
narration: "That covers the core workflow. You can now create, monitor, and analyze results from a single interface."
```

### Patterns to Avoid

```yaml
# Too vague
narration: "Here is something interesting."

# Too long
narration: "This feature allows you to configure multiple parameters across different sections including but not limited to the scoring threshold, the ensemble method, the temperature parameter, and several advanced options."

# Just describing the action
narration: "I am clicking the button."

# Breaking the fourth wall
narration: "As you can see in this demo video..."
```
