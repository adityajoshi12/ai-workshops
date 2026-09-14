// Bridges A2A's task/event lifecycle to the LangGraph agent. Structure
// mirrors @a2a-js/sdk's own sample-agent executor (task -> working ->
// artifact -> completed), swapping the canned reply for a real LLM call.

import { Role, TaskState } from "@a2a-js/sdk";
import { AgentEvent } from "@a2a-js/sdk/server";
import { runHotelAgent } from "./agent.js";

function extractText(message) {
  const textPart = message.parts.find((part) => part.content?.$case === "text");
  return textPart?.content?.$case === "text" ? textPart.content.value.trim() : "";
}

export class HotelSearchAgentExecutor {
  cancelledTasks = new Set();

  cancelTask = async (taskId) => {
    this.cancelledTasks.add(taskId);
  };

  async execute(requestContext, eventBus) {
    const { userMessage, task: existingTask, taskId, contextId } = requestContext;

    const taskSnapshot = existingTask ?? {
      id: taskId,
      contextId,
      status: { state: TaskState.TASK_STATE_SUBMITTED, timestamp: new Date().toISOString() },
      artifacts: [],
      history: [userMessage],
      metadata: userMessage.metadata,
    };
    eventBus.publish(AgentEvent.task(taskSnapshot));

    eventBus.publish(
      AgentEvent.statusUpdate({
        taskId,
        contextId,
        status: {
          state: TaskState.TASK_STATE_WORKING,
          timestamp: new Date().toISOString(),
          message: {
            role: Role.ROLE_AGENT,
            messageId: crypto.randomUUID(),
            taskId,
            contextId,
            parts: [
              {
                content: { $case: "text", value: "Searching hotels..." },
                filename: "",
                mediaType: "text/plain",
              },
            ],
            extensions: [],
            metadata: {},
            referenceTaskIds: [],
          },
        },
      })
    );

    const query = extractText(userMessage) || "Find some hotels.";
    let replyText;
    try {
      replyText = await runHotelAgent(query);
    } catch (err) {
      eventBus.publish(
        AgentEvent.statusUpdate({
          taskId,
          contextId,
          status: {
            state: TaskState.TASK_STATE_FAILED,
            timestamp: new Date().toISOString(),
            message: undefined,
          },
          metadata: { error: String(err?.message ?? err) },
        })
      );
      return;
    }

    if (this.cancelledTasks.has(taskId)) {
      eventBus.publish(
        AgentEvent.statusUpdate({
          taskId,
          contextId,
          status: { state: TaskState.TASK_STATE_CANCELED, timestamp: new Date().toISOString() },
        })
      );
      this.cancelledTasks.delete(taskId);
      return;
    }

    eventBus.publish(
      AgentEvent.artifactUpdate({
        taskId,
        contextId,
        artifact: {
          artifactId: crypto.randomUUID(),
          name: "Result",
          description: "Hotel search results (mock data).",
          parts: [
            { content: { $case: "text", value: replyText }, filename: "", mediaType: "text/plain" },
          ],
          extensions: [],
        },
        lastChunk: true,
        append: false,
      })
    );

    eventBus.publish(
      AgentEvent.statusUpdate({
        taskId,
        contextId,
        status: { state: TaskState.TASK_STATE_COMPLETED, timestamp: new Date().toISOString() },
      })
    );

    this.cancelledTasks.delete(taskId);
  }
}
