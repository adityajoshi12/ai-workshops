# Deploying a Google ADK Agent to Cloud Run

This guide shows how to deploy a Google ADK agent to Cloud Run, create a session, and invoke the agent.

## Prerequisites

* Google Cloud project
* Cloud Run API enabled
* Google ADK installed
* A valid Gemini API key

---

## Deploy the Agent

Deploy the `research_assistant` agent to Cloud Run:

```bash
adk deploy cloud_run research_assistant -- \
  --region=asia-south1 \
  --set-env-vars=GOOGLE_CLOUD_PROJECT=gde-workspace,\
GOOGLE_CLOUD_LOCATION=asia-south1,\
GOOGLE_API_KEY=YOUR_GEMINI_API_KEY,\
GOOGLE_GENAI_USE_VERTEXAI=FALSE
```

> **Note**
>
> Replace `YOUR_GEMINI_API_KEY` with your actual Gemini Developer API key.

After deployment, note the Cloud Run service URL. It will look similar to:

```text
https://adk-default-service-name-1012561205562.asia-south1.run.app
```

---

# Create a Session

Before interacting with the agent, create a session.

```bash
curl -X POST \
"https://adk-default-service-name-1012561205562.asia-south1.run.app/apps/research_assistant/users/u_123/sessions/s_1234" \
-H "Content-Type: application/json" \
-d '{
  "key1": "value1",
  "key2": "value2"
}'
```

Expected response:

```json
{
  "id": "s_1234",
  "appName": "research_assistant",
  "userId": "u_123"
}
```

---

# Invoke the Agent

Send a message to the agent using the `/run` endpoint.

```bash
curl -X POST \
"https://adk-default-service-name-1012561205562.asia-south1.run.app/run" \
-H "Content-Type: application/json" \
-d '{
  "appName": "research_assistant",
  "userId": "u_123",
  "sessionId": "s_1234",
  "newMessage": {
    "role": "user",
    "parts": [
      {
        "text": "Help me research Google Gemini."
      }
    ]
  }
}'
```

The response contains the agent's generated messages along with any tool execution events.

---

## Configuration

The deployment above uses the **Gemini Developer API**.

| Environment Variable        | Description                                    |
| --------------------------- | ---------------------------------------------- |
| `GOOGLE_API_KEY`            | Gemini Developer API key                       |
| `GOOGLE_GENAI_USE_VERTEXAI` | Set to `FALSE` to use the Gemini Developer API |
| `GOOGLE_CLOUD_PROJECT`      | Google Cloud project ID                        |
| `GOOGLE_CLOUD_LOCATION`     | Cloud Run deployment region                    |

If you plan to use **Vertex AI** instead of the Gemini Developer API:

* Remove `GOOGLE_API_KEY`
* Set `GOOGLE_GENAI_USE_VERTEXAI=TRUE`
* Ensure the Cloud Run service account has the required Vertex AI permissions.
