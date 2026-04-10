# Scenario Format

Scenarios are YAML files that define a sequence of browser actions with optional narration.

## Top-Level Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `title` | string | **required** | Scenario title (used in manifest and outputs) |
| `base_url` | string | `http://localhost:8080` | Base URL for relative navigation paths |
| `resolution` | [int, int] | `[1920, 1080]` | Browser viewport width and height in pixels |
| `pause_between_steps` | float | `1.5` | Default hold time per step in seconds |
| `transition` | string | `fade` | Transition style (reserved for future use) |
| `voice` | string | `onyx` | Default TTS voice (used as OpenAI fallback) |
| `tts_model` | string | `tts-1-hd` | OpenAI TTS model name |
| `steps` | list | **required** | Ordered list of step definitions |

## Step Actions

| Action | Description | Key Fields |
|---|---|---|
| `navigate` | Navigate to a URL | `url` |
| `click` | Click an element | `selector` |
| `type` | Type text into an input field | `selector`, `text` |
| `hover` | Hover over an element | `selector` |
| `scroll` | Scroll the page or an element | `selector` (optional), `distance` |
| `wait` | Wait for a specified duration | `wait_seconds` |
| `screenshot` | Capture a screenshot (no browser action) | -- |

## Step Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `action` | string | **required** | One of: `navigate`, `click`, `type`, `hover`, `scroll`, `wait`, `screenshot` |
| `url` | string | None | URL for `navigate` action. Relative paths are prepended with `base_url`. |
| `selector` | string | None | CSS selector for `click`, `type`, `hover`, `scroll` actions |
| `text` | string | None | Text to type for `type` action |
| `distance` | int | `0` | Scroll distance in pixels for `scroll` action |
| `narration` | string | `""` | TTS voiceover text for this step |
| `highlight` | string | None | CSS selector for an element to outline with a blue border |
| `wait_for` | string | None | CSS selector to wait for before capturing the screenshot |
| `wait_seconds` | float | `0.0` | Duration in seconds for `wait` action |
| `duration_override` | float | None | Override the default `pause_between_steps` for this step |

!!! tip "Narration on every step"
    Add a `narration` field to every step for continuous voiceover. Steps without narration produce silent segments.

!!! tip "Highlighting"
    Use `highlight` with a CSS selector to draw a blue outline (`3px solid #4f86f7`) around an element before the screenshot is captured. The highlight is removed after capture.

## Example: Basic Walkthrough

```yaml
title: "Basic Webapp Walkthrough"
base_url: "http://localhost:8080"
resolution: [1920, 1080]
pause_between_steps: 2.0
voice: "onyx"

steps:
  - action: navigate
    url: /
    narration: "Welcome to the application. This is the landing page."
    wait_for: "body"

  - action: screenshot
    narration: "Here you can see the main navigation and dashboard overview."
```

## Example: Multi-Step Form Flow

```yaml
title: "User Registration Flow"
base_url: "https://app.example.com"
resolution: [1920, 1080]
pause_between_steps: 1.5

steps:
  - action: navigate
    url: /register
    narration: "Open the registration page."
    wait_for: "#register-form"

  - action: type
    selector: "#email"
    text: "demo@example.com"
    narration: "Enter the email address."
    highlight: "#email"

  - action: type
    selector: "#password"
    text: "SecurePassword123"
    narration: "Set a password."

  - action: click
    selector: "#terms-checkbox"
    narration: "Accept the terms of service."

  - action: click
    selector: "button[type=submit]"
    narration: "Submit the registration form."
    highlight: "button[type=submit]"

  - action: wait
    wait_seconds: 3.0
    narration: "The system processes the registration."

  - action: screenshot
    narration: "Registration is complete. The dashboard is now visible."
    wait_for: ".dashboard"
    duration_override: 4.0
```

## Example: Scroll and Hover

```yaml
title: "Scroll and Hover Demo"
base_url: "http://localhost:3000"

steps:
  - action: navigate
    url: /features
    narration: "Navigate to the features page."

  - action: scroll
    distance: 500
    narration: "Scroll down to see more features."

  - action: hover
    selector: ".feature-card:nth-child(2)"
    narration: "Hover over the second feature card to reveal details."
    highlight: ".feature-card:nth-child(2)"

  - action: scroll
    selector: ".sidebar"
    distance: 300
    narration: "Scroll the sidebar to see additional options."
```
