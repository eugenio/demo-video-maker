# TTS Backends

demo-video-maker supports four text-to-speech backends. Select one with the `--tts` flag.

## Kokoro (default)

Local inference using Kokoro ONNX models. No API key required. Model files are downloaded automatically on first use (~80 MB) and cached in `~/.cache/kokoro-onnx/`.

```bash
demo-video-maker record scenario.yaml --tts kokoro --voice af_heart
```

**Default voice:** `af_heart`

**Available voices:**

| Voice | Description |
|---|---|
| `af_heart` | Female (American) |
| `af_alloy` | Female (American) |
| `af_aoede` | Female (American) |
| `af_bella` | Female (American) |
| `af_jessica` | Female (American) |
| `af_kore` | Female (American) |
| `af_nicole` | Female (American) |
| `af_nova` | Female (American) |
| `af_river` | Female (American) |
| `af_sarah` | Female (American) |
| `af_sky` | Female (American) |
| `am_adam` | Male (American) |
| `am_echo` | Male (American) |
| `am_eric` | Male (American) |
| `am_fenrir` | Male (American) |
| `am_liam` | Male (American) |
| `am_michael` | Male (American) |
| `am_onyx` | Male (American) |
| `am_puck` | Male (American) |
| `am_santa` | Male (American) |
| `bf_emma` | Female (British) |
| `bf_isabella` | Female (British) |
| `bm_george` | Male (British) |
| `bm_lewis` | Male (British) |
| `bm_daniel` | Male (British) |
| `if_sara` | Female (Italian) |
| `im_nicola` | Male (Italian) |

**Language codes:** `en-us`, `en-gb`, `it`, `fr`, `es`, `ja`, `zh`, `hi`, `pt-br`

!!! tip
    Voice name prefixes indicate accent and gender: `af_` = American female, `am_` = American male, `bf_` = British female, `bm_` = British male, `if_` = Italian female, `im_` = Italian male.

---

## OpenAI

Cloud-based TTS via the OpenAI API. Requires the `OPENAI_API_KEY` environment variable.

```bash
export OPENAI_API_KEY="sk-..."
demo-video-maker record scenario.yaml --tts openai --voice nova
```

**Default voice:** `onyx` (or the `voice` field from the scenario YAML)

**Model:** `tts-1-hd` (configurable via the `tts_model` scenario field)

**Available voices:**

`alloy`, `ash`, `ballad`, `coral`, `echo`, `fable`, `nova`, `onyx`, `sage`, `shimmer`

!!! warning "API costs"
    OpenAI TTS is a paid API. Each step with narration incurs a charge based on character count.

---

## Edge TTS

Microsoft Edge text-to-speech. Free, no API key required. Uses the `edge-tts` Python package.

```bash
demo-video-maker record scenario.yaml --tts edge --voice en-US-AvaMultilingualNeural
```

**Default voice:** `en-US-AvaMultilingualNeural`

**Available voices (selection):**

| Voice | Language |
|---|---|
| `en-US-AvaMultilingualNeural` | English (US) |
| `en-US-AndrewMultilingualNeural` | English (US) |
| `en-US-EmmaMultilingualNeural` | English (US) |
| `en-US-BrianMultilingualNeural` | English (US) |
| `en-US-JennyNeural` | English (US) |
| `en-US-GuyNeural` | English (US) |
| `en-US-AriaNeural` | English (US) |
| `en-US-DavisNeural` | English (US) |
| `en-US-JaneNeural` | English (US) |
| `en-US-JasonNeural` | English (US) |
| `en-US-SaraNeural` | English (US) |
| `en-US-TonyNeural` | English (US) |
| `en-US-NancyNeural` | English (US) |
| `en-GB-SoniaNeural` | English (UK) |
| `en-GB-RyanNeural` | English (UK) |

!!! note
    Edge TTS supports hundreds of voices across many languages. Run `edge-tts --list-voices` to see the full list.

---

## Silent

Generates silent audio files with durations estimated from word count (~150 words per minute). Useful for testing the pipeline without TTS overhead.

```bash
demo-video-maker record scenario.yaml --tts silent
```

No configuration options. Minimum duration is 2 seconds per step.

---

## Choosing a Backend

| Backend | Quality | Speed | Cost | API Key |
|---|---|---|---|---|
| Kokoro | High | Moderate | Free | No |
| OpenAI | Very high | Fast | Paid | Yes |
| Edge TTS | High | Fast | Free | No |
| Silent | N/A | Instant | Free | No |

For most use cases, **Kokoro** provides the best balance of quality and convenience. Use **OpenAI** when you need the highest quality voices. Use **Edge TTS** when you need multilingual support with zero setup.
