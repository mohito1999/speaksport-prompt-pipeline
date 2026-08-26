# SpeakSport Control Room

The Control Room is the local, form-based interface for facility provisioning and prompt updates. It creates the same validated project files as the command-line workflow, without requiring anyone to hand-edit YAML.

## Start it

On this Mac, double-click `start-control-room.command` in the project folder. A Terminal window stays open while the Control Room is running, and the browser opens automatically.

The terminal alternative is:

```bash
source .venv/bin/activate
speaksport ui
```

Then open `http://127.0.0.1:8765`. Press Control-C in the Terminal window to stop it.

The server listens only on this computer by default. Credentials remain in the local `.env` file and are never displayed in the interface.

## Create a new facility

1. Open **New facility**.
2. Enter the facility basics and choose the integration and tee sheet.
3. Configure the course layout, optional single-player pairing rule, transfer guardrail, pricing model, tools, transfer destinations, and policies.
4. Select **Save facility**. The Control Room validates the configuration and writes `facility.yaml` plus the supporting notes files together.
5. Review the external-processing message. Check the approval box only when the facility materials are ready to be sent to Firecrawl and OpenRouter, then start the run.
6. Follow live progress under **Run history**.

Club Prophet automatically selects and locks the customer-record and identity-confirmation tools. Non-integrated setups switch to the appropriate SMS-oriented tool recommendations. Existing facilities can be opened with **Edit**, so the same form handles later configuration changes.

## Update an existing customer prompt

1. Open **Prompt update**.
2. Paste the production prompt or choose a local Markdown/text file.
3. Describe the requested changes in plain language.
4. Configure the tee sheet, tools, transfer destinations, course behavior, preservation mode, and validation markers.
5. Save the update workspace, approve OpenRouter processing, and start the run.

The original prompt and update instructions remain in the separate `modifications/<slug>/` workflow. Existing prompt updates can also be reopened with **Edit**. Modification runs continue to produce the review package and original-versus-updated diff under `modification-runs/`.

## Review prior work

**Overview** shows saved facility and update workspaces plus recent activity. **Run history** automatically discovers existing new-facility and modification runs already stored in the repository. Filter or search by facility, open generated prompts and QA artifacts, and watch active jobs without finding folders manually.

The UI never publishes a prompt to Vapi. Human review and approval remain mandatory after a pipeline run completes.
