"use client";

import { useMemo, useState } from "react";

import { sendChat } from "@/lib/api";
import type { ChatResponse, PlanRequest } from "@/lib/types";

type ChatAssistantPanelProps = {
  planning: boolean;
  onGeneratePlan: (payload: PlanRequest) => Promise<void> | void;
};

function missingFieldLabel(key: string): string {
  const labels: Record<string, string> = {
    interests: "Interests",
    fusion_domain: "Fusion Domain",
    preferred_role_id: "Preferred Role",
  };
  return labels[key] ?? key;
}

export default function ChatAssistantPanel({
  planning,
  onGeneratePlan,
}: ChatAssistantPanelProps): JSX.Element {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [message, setMessage] = useState<string>(
    "I am an undergraduate interested in finance and analytics."
  );
  const [chatState, setChatState] = useState<ChatResponse | null>(null);
  const [sending, setSending] = useState<boolean>(false);
  const [error, setError] = useState<string>("");

  const chatDisabled = sending || planning;
  const draftReady = !!chatState?.plan_request_draft && chatState.ready_for_plan;

  const rolePreview = useMemo(() => {
    if (!chatState?.suggested_roles?.length) {
      return "No role suggestions yet.";
    }
    return chatState.suggested_roles
      .slice(0, 3)
      .map((item) => item.title)
      .join(", ");
  }, [chatState]);

  async function handleSend(resetSession = false): Promise<void> {
    const content = message.trim();
    if (!content) {
      return;
    }
    setSending(true);
    setError("");
    try {
      const response = await sendChat({
        message: content,
        session_id: sessionId,
        reset_session: resetSession,
      });
      setSessionId(response.session_id);
      setChatState(response);
      setMessage("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to send chat message.");
    } finally {
      setSending(false);
    }
  }

  async function handleGenerateFromDraft(): Promise<void> {
    if (!chatState?.plan_request_draft) {
      return;
    }
    await onGeneratePlan(chatState.plan_request_draft);
  }

  return (
    <section className="panel chat-panel">
      <div className="panel-header">
        <h2>Conversational Intake</h2>
        <p>
          Multi-turn chat that extracts profile details and prepares a plan draft.
        </p>
      </div>

      {error ? <p className="error-line">{error}</p> : null}

      <div className="chat-window">
        {chatState?.conversation?.length ? (
          chatState.conversation.map((turn, idx) => (
            <div
              key={`${turn.timestamp_utc}-${idx}`}
              className={`chat-line ${turn.role === "assistant" ? "assistant" : "user"}`}
            >
              <p className="chat-role">{turn.role === "assistant" ? "Sanjaya AI" : "You"}</p>
              <p>{turn.content}</p>
            </div>
          ))
        ) : (
          <p className="muted">Start by telling your background and interests.</p>
        )}
      </div>

      <div className="chat-controls">
        <input
          type="text"
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder="Type your message..."
          disabled={chatDisabled}
        />
        <button
          type="button"
          className="btn-primary"
          disabled={chatDisabled || !message.trim()}
          onClick={() => void handleSend(false)}
        >
          {sending ? "Sending..." : "Send"}
        </button>
        <button
          type="button"
          className="btn-secondary"
          disabled={chatDisabled}
          onClick={() => {
            setSessionId(null);
            setChatState(null);
            setMessage("Let's start over with a new intake.");
          }}
        >
          Clear
        </button>
      </div>

      {chatState ? (
        <article className="subpanel">
          <h3>Chat Extracted Draft</h3>
          <p className="muted">
            LLM extraction: {chatState.llm_used ? "enabled" : "fallback heuristic"}
          </p>
          <p className="muted">
            Suggested roles: <strong>{rolePreview}</strong>
          </p>
          {chatState.missing_fields.length ? (
            <p className="muted">
              Missing:{" "}
              {chatState.missing_fields.map(missingFieldLabel).join(", ")}
            </p>
          ) : (
            <p className="muted">Profile has enough details for planning.</p>
          )}

          <div className="chat-actions">
            <button
              type="button"
              className="btn-primary"
              disabled={!draftReady || planning}
              onClick={() => void handleGenerateFromDraft()}
            >
              {planning ? "Generating..." : "Generate Plan From Chat Draft"}
            </button>
            <button
              type="button"
              className="btn-secondary"
              disabled={chatDisabled}
              onClick={() => {
                setMessage("Please summarize my current profile and what is missing.");
                void handleSend(false);
              }}
            >
              Ask For Summary
            </button>
          </div>
        </article>
      ) : null}
    </section>
  );
}
