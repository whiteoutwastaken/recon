"use client";

import { useState, useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import { X, Mic, MicOff, Send, MessageSquare, Sparkles } from "lucide-react";
import { queryAgent, fetchBriefing } from "@/lib/api";

interface VoiceAgentPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

const suggestedQuestions = [
  "Why did you flag this pattern?",
  "Compare OpenAI vs Anthropic",
  "Give me a 2-minute CEO briefing",
  "What's the biggest competitive threat?",
  "Summarize the latest hiring signals",
];

// Extend Window type for SpeechRecognition
declare global {
  interface Window {
    SpeechRecognition: any;
    webkitSpeechRecognition: any;
  }
}

export function VoiceAgentPanel({ isOpen, onClose }: VoiceAgentPanelProps) {
  const [isListening, setIsListening] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      role: "assistant",
      content: "Hello! I'm Recon, your AI competitive intelligence assistant. Click the mic or type to ask me anything about your competitors.",
      timestamp: "Just now",
    },
  ]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [voiceSupported, setVoiceSupported] = useState(false);
  const recognitionRef = useRef<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Check browser support and set up recognition
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      setVoiceSupported(true);
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = "en-US";

      recognition.onresult = (event: any) => {
        let interim = "";
        let final = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const t = event.results[i][0].transcript;
          if (event.results[i].isFinal) final += t;
          else interim += t;
        }
        setTranscript(interim || final);
        if (final) {
          setInputValue(final);
          setTranscript("");
        }
      };

      recognition.onend = () => {
        setIsListening(false);
        setTranscript("");
      };

      recognition.onerror = (event: any) => {
        setIsListening(false);
        setTranscript("");
        if (event.error === "network") {
          setVoiceSupported(false);
          setMessages((prev) => [...prev, {
            id: Date.now().toString(),
            role: "assistant" as const,
            content: "Voice input requires an internet connection — Chrome sends audio to Google for processing. Please type your question instead.",
            timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          }]);
        } else if (event.error === "not-allowed") {
          setMessages((prev) => [...prev, {
            id: Date.now().toString(),
            role: "assistant" as const,
            content: "Microphone access was denied. Please allow mic permissions in your browser settings and try again.",
            timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          }]);
        }
      };

      recognitionRef.current = recognition;
    }

    return () => {
      recognitionRef.current?.abort();
    };
  }, []);

  // Auto scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const toggleListening = () => {
    if (!recognitionRef.current) return;
    if (isListening) {
      recognitionRef.current.stop();
      setIsListening(false);
    } else {
      setInputValue("");
      setTranscript("");
      recognitionRef.current.start();
      setIsListening(true);
    }
  };

  const handleSend = async (overrideQuery?: string) => {
    const q = (overrideQuery || inputValue).trim();
    if (!q || isLoading) return;

    // Stop listening if active
    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
    }

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: q,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInputValue("");
    setTranscript("");
    setIsLoading(true);

    try {
      let answer: string;

      if (q.toLowerCase().includes("briefing")) {
        const data = await fetchBriefing();
        answer = data.text || data.response || "Could not generate briefing.";
      } else {
        const data = await queryAgent(q);
        answer = data.answer || data.error || "No response.";
        if (data.suggested_followups?.length) {
          answer += "\n\nFollow-up questions:\n" + data.suggested_followups.map((f: string) => `• ${f}`).join("\n");
        }
      }

      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: answer,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: "Could not reach the backend. Make sure Flask is running on port 5000.",
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    }

    setIsLoading(false);
  };

  const handleSuggested = (q: string) => {
    handleSend(q);
  };

  // Auto-send when transcript is final and mic stops
  useEffect(() => {
    if (inputValue && !isListening && !isLoading) {
      // Small delay so user can see what was transcribed before sending
      const timer = setTimeout(() => handleSend(), 600);
      return () => clearTimeout(timer);
    }
  }, [isListening]);

  return (
    <div
      className={cn(
        "fixed right-0 top-16 h-[calc(100vh-64px)] w-[360px] bg-sidebar border-l border-sidebar-border z-50 flex flex-col transition-transform duration-300 ease-out shadow-2xl",
        isOpen ? "translate-x-0" : "translate-x-full"
      )}
    >
      {/* Header */}
      <div className="h-14 px-4 flex items-center justify-between border-b border-sidebar-border flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-foreground flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-background" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-foreground">Recon AI</h3>
            <p className="text-xs text-muted-foreground">Competitive Intelligence</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="w-8 h-8 flex items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-secondary transition-all"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Voice button area */}
      <div className="p-4 border-b border-sidebar-border flex-shrink-0">
        <div className="flex items-center justify-center gap-4">
          <button
            onClick={toggleListening}
            disabled={!voiceSupported}
            className={cn(
              "relative w-16 h-16 rounded-full flex items-center justify-center transition-all duration-300",
              isListening
                ? "bg-foreground text-background scale-110"
                : voiceSupported
                ? "bg-secondary text-muted-foreground hover:text-foreground hover:bg-secondary/80"
                : "bg-secondary/30 text-muted-foreground/30 cursor-not-allowed"
            )}
          >
            {isListening ? <Mic className="w-7 h-7" /> : <MicOff className="w-7 h-7" />}
            {isListening && (
              <>
                <span className="absolute inset-0 rounded-full bg-foreground/30 animate-ping" />
                <span className="absolute -inset-2 rounded-full border-2 border-foreground/20 animate-pulse" />
              </>
            )}
          </button>
          <div className="flex flex-col items-start">
            <span className={cn("text-sm font-medium", isListening ? "text-foreground" : "text-muted-foreground")}>
              {!voiceSupported ? "Voice not supported" : isListening ? "Listening..." : "Click to speak"}
            </span>
            <span className="text-xs text-muted-foreground">
              {isListening ? "Speak now, auto-sends when done" : "Or type below"}
            </span>
          </div>
        </div>

        {/* Live transcript display */}
        {(isListening || transcript) && (
          <div className="mt-3 p-2 rounded-lg bg-secondary/50 border border-border min-h-[32px]">
            <p className="text-xs text-muted-foreground italic">
              {transcript || "Listening..."}
            </p>
          </div>
        )}

        {/* Audio visualizer when listening */}
        {isListening && (
          <div className="mt-3 flex items-center justify-center gap-0.5 h-8">
            {Array.from({ length: 24 }).map((_, i) => (
              <div
                key={i}
                className="w-1 bg-foreground/60 rounded-full animate-pulse"
                style={{
                  height: `${Math.random() * 20 + 4}px`,
                  animationDelay: `${i * 40}ms`,
                  animationDuration: `${0.6 + Math.random() * 0.6}s`,
                }}
              />
            ))}
          </div>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <div
            key={message.id}
            className={cn(
              "flex gap-3 animate-in fade-in slide-in-from-bottom-2",
              message.role === "user" && "flex-row-reverse"
            )}
          >
            <div
              className={cn(
                "w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5",
                message.role === "assistant" ? "bg-foreground" : "bg-secondary"
              )}
            >
              {message.role === "assistant" ? (
                <Sparkles className="w-3.5 h-3.5 text-background" />
              ) : (
                <MessageSquare className="w-3.5 h-3.5 text-muted-foreground" />
              )}
            </div>
            <div
              className={cn(
                "flex-1 p-3 rounded-lg text-sm",
                message.role === "assistant"
                  ? "bg-secondary/50 text-foreground"
                  : "bg-foreground/10 text-foreground border border-border"
              )}
            >
              <p className="leading-relaxed whitespace-pre-wrap">{message.content}</p>
              <span className="text-xs text-muted-foreground mt-1.5 block">{message.timestamp}</span>
            </div>
          </div>
        ))}

        {/* Loading indicator */}
        {isLoading && (
          <div className="flex gap-3">
            <div className="w-7 h-7 rounded-full bg-foreground flex items-center justify-center shrink-0">
              <Sparkles className="w-3.5 h-3.5 text-background" />
            </div>
            <div className="flex-1 p-3 rounded-lg bg-secondary/50">
              <div className="flex items-center gap-1.5">
                {[0, 1, 2].map((i) => (
                  <div
                    key={i}
                    className="w-2 h-2 rounded-full bg-muted-foreground animate-bounce"
                    style={{ animationDelay: `${i * 150}ms` }}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Suggested questions */}
      <div className="px-4 py-3 border-t border-sidebar-border flex-shrink-0">
        <p className="text-xs text-muted-foreground mb-2">Suggested:</p>
        <div className="flex flex-wrap gap-1.5">
          {suggestedQuestions.slice(0, 3).map((q) => (
            <button
              key={q}
              onClick={() => handleSuggested(q)}
              disabled={isLoading}
              className="px-2.5 py-1 rounded-md bg-secondary text-xs text-muted-foreground hover:text-foreground hover:bg-secondary/80 transition-all disabled:opacity-40 text-left"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* Text input */}
      <div className="p-4 border-t border-sidebar-border flex-shrink-0">
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder={isListening ? "Listening..." : "Type a message..."}
            disabled={isListening}
            className="flex-1 h-10 px-3 rounded-lg bg-secondary border border-border text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-accent transition-all disabled:opacity-50"
          />
          <button
            onClick={() => handleSend()}
            disabled={!inputValue.trim() || isLoading || isListening}
            className="w-10 h-10 flex items-center justify-center rounded-lg bg-foreground text-background hover:bg-foreground/90 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}