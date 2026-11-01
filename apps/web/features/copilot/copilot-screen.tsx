"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleAlert, Clock, Loader, MessagesSquare, Plus, Send, Sparkles } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";

import { PageHeader } from "@/components/shell/page-header";
import { ErrorState } from "@/components/states/error-state";
import { PermissionDenied } from "@/components/states/permission-denied";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { copilotApi, copilotKeys, type Conversation, type ConversationDetail, type CopilotMessage } from "@/lib/api/copilot-api";
import { isApiError, userMessage } from "@/lib/api/errors";
import { formatRelative } from "@/lib/format/datetime";
import { useCountdown } from "@/lib/hooks/use-countdown";
import { useDocumentTitle } from "@/lib/hooks/use-document-title";
import { useNow } from "@/lib/hooks/use-now";
import { useStore } from "@/lib/store/store-context";
import { cn } from "@/lib/utils";

import { CopilotAnswer, Provenance } from "./copilot-answer";

export const QUESTION_LIMIT = 1000;
const COUNTER_FROM = 800;
const TIMEOUT_MS = 60_000;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const SUGGESTED_QUESTIONS = [
  "What should I work on first today?",
  "Which orders are overdue, and why?",
  "Which products could run out before their restock arrives?",
  "Summarise the oversold products and the orders they affect.",
  "What went wrong in the last import?",
  "How has fulfillment performance changed over the last 30 days?",
];

/** The question's problem, if any (S-14 "Validation error"). */
export function questionProblem(question: string): string | null {
  if (!question.trim()) return "Type a question first.";
  if (question.length > QUESTION_LIMIT) return "Questions are limited to 1,000 characters.";
  return null;
}

function ConversationList({
  conversations,
  selectedId,
  onSelect,
  onNew,
}: {
  conversations: { data?: { items: Conversation[] }; isPending: boolean; isError: boolean; error: unknown; refetch: () => unknown };
  selectedId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
}) {
  const store = useStore();
  const now = useNow();
  return (
    <div className="flex min-h-0 flex-col gap-3">
      <Button type="button" variant="secondary" onClick={onNew}>
        <Plus aria-hidden />
        New conversation
      </Button>
      {conversations.isPending ? (
        <div aria-busy="true" className="flex flex-col gap-2">
          {[0, 1, 2, 3, 4, 5].map((row) => (
            <Skeleton key={row} className="h-12 w-full" />
          ))}
        </div>
      ) : conversations.isError ? (
        <ErrorState title="Couldn't load conversations" error={conversations.error} onRetry={() => void conversations.refetch()} />
      ) : conversations.data?.items.length ? (
        <ul aria-label="Conversations" className="flex flex-col gap-1">
          {conversations.data.items.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                aria-current={item.id === selectedId ? "true" : undefined}
                onClick={() => onSelect(item.id)}
                className={cn(
                  "flex w-full flex-col gap-0.5 rounded-md px-2 py-1.5 text-left hover:bg-accent",
                  item.id === selectedId && "bg-surface-selected",
                )}
              >
                <span className="line-clamp-1 text-body">{item.title}</span>
                <span className="flex items-center gap-2 text-xs text-muted-foreground">
                  {item.context_type === "EXCEPTION" ? <span className="rounded-sm border px-1">Exception</span> : null}
                  {formatRelative(item.updated_at, store.timezone, now)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">No conversations yet.</p>
      )}
    </div>
  );
}

function MessageView({ message }: { message: CopilotMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex flex-col gap-1">
        <span className="text-xs font-medium text-muted-foreground">You</span>
        <p className="text-body whitespace-pre-line">{message.text}</p>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-medium text-muted-foreground">
        Copilot{message.kind === "INVESTIGATION_SUMMARY" ? " · Investigation summary" : message.kind === "NOTE_DRAFT" ? " · Note draft (not saved)" : ""}
      </span>
      {message.answer ? (
        <CopilotAnswer answer={message.answer} meta={message.meta} createdAt={message.created_at} />
      ) : message.draft ? (
        <div className="flex flex-col gap-2">
          <p className="rounded-md border bg-surface-subtle p-3 text-body whitespace-pre-line">{message.draft.body}</p>
          <Provenance answer={message.draft} meta={message.meta} createdAt={message.created_at} />
        </div>
      ) : null}
    </div>
  );
}

function Pending() {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const timer = window.setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, []);
  return (
    <div role="status" className="flex items-center gap-2 text-body text-muted-foreground">
      <Loader aria-hidden className="size-4 animate-spin motion-reduce:animate-none" />
      Gathering data… <span className="tabular-nums">{seconds} s</span>
    </div>
  );
}

/** Plain-language questions about this store, answered from read-only tools (SCREEN_SPECIFICATIONS S-14). */
export function CopilotScreen() {
  const store = useStore();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  useDocumentTitle("Copilot");
  const canUse = store.permissions.has("copilot.use");

  const selectedParam = searchParams.get("c");
  const selectedId = selectedParam && UUID.test(selectedParam) ? selectedParam : null;
  const contextId = searchParams.get("context_type") === "EXCEPTION" ? searchParams.get("context_id") : null;
  const exceptionContext = contextId && UUID.test(contextId) ? contextId : null;

  const [question, setQuestion] = useState(() => (searchParams.get("q") ?? "").slice(0, QUESTION_LIMIT));
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);
  const [showProblem, setShowProblem] = useState(false);
  const [listOpen, setListOpen] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const composerId = useId();
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const conversations = useQuery({
    queryKey: copilotKeys.conversations(store.id),
    queryFn: ({ signal }) => copilotApi.conversations(store.id, signal),
    enabled: canUse,
  });
  const thread = useQuery({
    queryKey: copilotKeys.conversation(store.id, selectedId ?? ""),
    queryFn: ({ signal }) => copilotApi.conversation(store.id, selectedId as string, signal),
    enabled: canUse && selectedId !== null,
  });

  const ask = useMutation({
    mutationFn: async (text: string) => {
      let conversationId = selectedId;
      if (!conversationId) {
        const created = await copilotApi.create(
          store.id,
          exceptionContext ? { context_type: "EXCEPTION", context_id: exceptionContext } : { context_type: "GENERAL" },
        );
        conversationId = created.id;
      }
      const timeout = new Promise<never>((_, reject) =>
        window.setTimeout(() => reject(new Error("The copilot took too long to answer. Try again.")), TIMEOUT_MS),
      );
      await Promise.race([copilotApi.ask(store.id, conversationId, text), timeout]);
      return conversationId;
    },
    onSuccess: async (conversationId) => {
      setQuestion("");
      setPendingQuestion(null);
      setAnnouncement("Answer ready");
      await queryClient.invalidateQueries({ queryKey: copilotKeys.conversations(store.id) });
      if (conversationId !== selectedId) router.replace(`${pathname}?c=${conversationId}`, { scroll: false });
    },
  });

  const rateLimited = isApiError(ask.error) && ask.error.status === 429;
  const secondsLeft = useCountdown(rateLimited ? (isApiError(ask.error) ? (ask.error.retryAfterSeconds ?? 60) : 60) : undefined, ask.error);
  const waiting = rateLimited && secondsLeft > 0;

  if (!canUse) return <PermissionDenied pageName="the copilot" permission="copilot.use" />;

  const select = (id: string) => {
    setListOpen(false);
    ask.reset();
    setPendingQuestion(null);
    router.replace(`${pathname}?c=${id}`, { scroll: false });
  };
  const startNew = () => {
    setListOpen(false);
    ask.reset();
    setPendingQuestion(null);
    setQuestion("");
    router.replace(pathname, { scroll: false });
  };
  const send = (text: string = question) => {
    const problem = questionProblem(text);
    setShowProblem(problem !== null);
    if (problem || ask.isPending || waiting) return;
    setAnnouncement("");
    setPendingQuestion(text);
    ask.mutate(text);
  };

  const problem = showProblem ? questionProblem(question) : question.length > QUESTION_LIMIT ? questionProblem(question) : null;
  const messages: CopilotMessage[] = thread.data?.messages ?? [];
  const detail: ConversationDetail | undefined = thread.data;
  const isEmpty = !selectedId && !pendingQuestion;
  const sendReason = ask.isPending ? "Wait for the answer to the current question." : waiting ? `Copilot limit reached. Try again in ${secondsLeft} s.` : null;

  const list = (
    <ConversationList conversations={conversations} selectedId={selectedId} onSelect={select} onNew={startNew} />
  );

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Copilot"
        subtitle={detail ? detail.title : "Ask about exceptions, orders, stock or imports."}
        actions={
          <Button type="button" variant="secondary" className="lg:hidden" onClick={() => setListOpen(true)}>
            <MessagesSquare aria-hidden />
            Conversations
          </Button>
        }
      />
      <Sheet open={listOpen} onOpenChange={setListOpen}>
        <SheetContent side="left" className="p-4">
          <SheetHeader className="p-0">
            <SheetTitle>Conversations</SheetTitle>
          </SheetHeader>
          {list}
        </SheetContent>
      </Sheet>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
        <aside aria-label="Conversations" className="hidden lg:block">
          <div className="sticky top-4">{list}</div>
        </aside>

        <section aria-label="Conversation" className="flex min-w-0 flex-col gap-4">
          {exceptionContext && !selectedId ? (
            <p className="text-sm text-muted-foreground">
              This conversation is about{" "}
              <Link href={`/s/${store.id}/exceptions/${exceptionContext}`} className="text-link hover:underline">
                the exception you came from
              </Link>
              .
            </p>
          ) : null}

          {isEmpty ? (
            <div className="flex flex-col gap-3 rounded-lg border bg-card p-5">
              <h2 className="flex items-center gap-2 text-title-sm">
                <Sparkles aria-hidden className="size-4 text-primary" />
                Ask about your operations
              </h2>
              <p className="text-body text-muted-foreground">Answers come from this store&apos;s data and list their sources.</p>
              <ul aria-label="Suggested questions" className="flex flex-wrap gap-2">
                {SUGGESTED_QUESTIONS.map((suggestion) => (
                  <li key={suggestion}>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      className="h-auto py-1 text-left whitespace-normal"
                      onClick={() => {
                        setQuestion(suggestion);
                        textareaRef.current?.focus();
                      }}
                    >
                      {suggestion}
                    </Button>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {selectedId && thread.isPending ? (
            <div aria-busy="true" className="flex flex-col gap-4">
              <Skeleton className="h-10 w-2/3" />
              <Skeleton className="h-40 w-full" />
            </div>
          ) : selectedId && thread.isError ? (
            <ErrorState title="Couldn't load this conversation" error={thread.error} onRetry={() => void thread.refetch()} />
          ) : (
            <ol aria-label="Messages" className="flex flex-col gap-5">
              {messages.map((message) => (
                <li key={message.id} className="rounded-lg border bg-card p-4">
                  <MessageView message={message} />
                </li>
              ))}
              {pendingQuestion && (ask.isPending || ask.isError) ? (
                <>
                  <li className="rounded-lg border bg-card p-4">
                    <div className="flex flex-col gap-1">
                      <span className="text-xs font-medium text-muted-foreground">You</span>
                      <p className="text-body whitespace-pre-line">{pendingQuestion}</p>
                    </div>
                  </li>
                  <li className="rounded-lg border bg-card p-4">
                    {ask.isPending ? (
                      <Pending />
                    ) : rateLimited ? null : (
                      <ErrorState
                        title={
                          ask.error instanceof Error && !isApiError(ask.error)
                            ? ask.error.message
                            : "The copilot couldn't answer. Your question was kept."
                        }
                        error={ask.error}
                        onRetry={() => send(pendingQuestion)}
                      />
                    )}
                  </li>
                </>
              ) : null}
            </ol>
          )}
          <div aria-live="polite" className="sr-only">
            {announcement}
          </div>

          <form
            onSubmit={(event) => {
              event.preventDefault();
              send();
            }}
            className="sticky bottom-0 -mx-1 flex flex-col gap-2 bg-background px-1 pt-2 pb-4"
          >
            {waiting ? (
              <Alert tone="warning">
                <Clock aria-hidden />
                <AlertDescription>
                  <p>Copilot limit reached. Try again in {secondsLeft} s.</p>
                </AlertDescription>
              </Alert>
            ) : null}
            {detail && detail.message_count >= detail.max_messages ? (
              <p className="text-sm text-muted-foreground">This conversation is full. Start a new conversation to keep asking.</p>
            ) : null}
            <div className="flex items-end gap-2">
              <label htmlFor={composerId} className="sr-only">
                Question
              </label>
              <Textarea
                ref={textareaRef}
                id={composerId}
                value={question}
                rows={1}
                placeholder="Ask about exceptions, orders, stock or imports…"
                aria-invalid={problem ? true : undefined}
                aria-describedby={problem ? `${composerId}-problem` : `${composerId}-note`}
                onChange={(event) => {
                  setQuestion(event.target.value);
                  setShowProblem(false);
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                    event.preventDefault();
                    send();
                  }
                }}
                className="max-h-36 min-h-9 flex-1 resize-none field-sizing-content"
              />
              {sendReason ? (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button type="submit" aria-disabled="true" aria-label="Send question" className="shrink-0">
                      <Send aria-hidden />
                      <span className="hidden sm:inline">Send</span>
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>{sendReason}</TooltipContent>
                </Tooltip>
              ) : (
                <Button type="submit" aria-label="Send question" className="shrink-0">
                  <Send aria-hidden />
                  <span className="hidden sm:inline">Send</span>
                </Button>
              )}
            </div>
            <div className="flex items-start justify-between gap-3">
              {problem ? (
                <p id={`${composerId}-problem`} role="alert" className="flex items-center gap-1 text-sm text-tone-danger-fg">
                  <CircleAlert aria-hidden className="size-4 shrink-0" />
                  {problem}
                </p>
              ) : (
                <p id={`${composerId}-note`} className="text-xs text-muted-foreground">
                  The copilot reads this store&apos;s data through read-only tools. It can&apos;t change data. Check references before acting.
                </p>
              )}
              {question.length >= COUNTER_FROM ? (
                <span className={cn("shrink-0 text-xs tabular-nums", question.length > QUESTION_LIMIT ? "text-tone-danger-fg" : "text-muted-foreground")}>
                  {question.length.toLocaleString("en-US")} / 1,000
                </span>
              ) : null}
            </div>
            {ask.isError && !rateLimited && isApiError(ask.error) && ask.error.code !== "NETWORK_ERROR" && ask.error.status < 500 ? (
              <p className="text-sm text-tone-danger-fg">{userMessage(ask.error)}</p>
            ) : null}
          </form>
        </section>
      </div>
    </div>
  );
}
