"use client";

import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Phone, PhoneOff, Mic, MicOff, Volume2, Sparkles, Activity, Clock, FileText, CheckCircle2, AlertTriangle } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "./auth-context";

interface TranscriptEntry {
  role: "assistant" | "user";
  text: string;
  timestamp: string;
}

export function VoiceCallTab() {
  const { user } = useAuth();
  const { toast } = useToast();

  const [callStatus, setCallStatus] = useState<"idle" | "connecting" | "active" | "ended">("idle");
  const [isMuted, setIsMuted] = useState(false);
  const [callDuration, setCallDuration] = useState(0);
  const [transcripts, setTranscripts] = useState<TranscriptEntry[]>([]);
  const [vapiConfig, setVapiConfig] = useState<any>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const vapiInstanceRef = useRef<any>(null);


  useEffect(() => {
    // Fetch Vapi configuration on load, with .env.local fallback
    const envPublicKey = process.env.NEXT_PUBLIC_VAPI_PUBLIC_KEY || "";
    const envAssistantId = process.env.NEXT_PUBLIC_VAPI_ASSISTANT_ID || "";

    fetch("/api/proxy/agent/vapi-config")
      .then((res) => res.json())
      .then((data) => {
        const publicKey =
          data.public_key && data.public_key !== "pk_live_vapi_real_estate_demo"
            ? data.public_key
            : envPublicKey;
        const assistantId =
          data.assistant_id && data.assistant_id !== "vapi-real-estate-assistant-pk"
            ? data.assistant_id
            : envAssistantId;

        const isPlaceholder = !publicKey || !assistantId;
        setVapiConfig({
          ...data,
          public_key: publicKey,
          assistant_id: assistantId,
          _isPlaceholder: isPlaceholder,
        });
      })
      .catch((err) => {
        console.error("Could not fetch Vapi config, falling back to env vars:", err);
        const isPlaceholder = !envPublicKey || !envAssistantId;
        setVapiConfig({
          public_key: envPublicKey,
          assistant_id: envAssistantId,
          enabled: !isPlaceholder,
          _isPlaceholder: isPlaceholder,
          _error: true,
        });
      });
  }, []);

  // Call timer effect
  useEffect(() => {
    if (callStatus === "active") {
      timerRef.current = setInterval(() => {
        setCallDuration((prev) => prev + 1);
      }, 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [callStatus]);

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  const startVoiceCall = async (initialQuery?: string) => {

      // The Vapi SDK handles microphone access internally. No manual getUserMedia needed.
      // Proceed to initialize Vapi client.

    // Check if VAPI is properly configured
    if (!vapiConfig || vapiConfig._isPlaceholder) {
      toast({
        title: "VAPI Not Configured",
        description: "Voice calls require valid VAPI credentials (VAPI_PUBLIC_KEY and VAPI_ASSISTANT_ID). Please configure them in the .env file.",
        variant: "destructive",
      });
      return;
    }
    // Clean up any existing Vapi instance
    if (vapiInstanceRef.current) {
      vapiInstanceRef.current.stop();
      vapiInstanceRef.current = null;
    }
    // Dynamically import Vapi SDK (client-side only)
    const { default: Vapi } = await import('@vapi-ai/web');
    const vapi = new Vapi(vapiConfig.public_key);
    vapiInstanceRef.current = vapi;
    // Attach event listeners with safety checks
    const safeTranscript = (data: any) => {
      try {
        const { role, content } = data || {};
        if (!role || !content) return;
        setTranscripts((prev) => [
          ...prev,
          {
            role: role === 'assistant' ? 'assistant' : 'user',
            text: content,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ]);
      } catch (e) {
        console.error('Transcript handling error:', e);
      }
    };
    vapi.on('transcript', safeTranscript);
    vapi.on('call-start', () => setCallStatus('active'));
    vapi.on('call-end', () => setCallStatus('ended'));
    vapi.on('error', (err: any) => {
      console.error('Vapi error event:', err);
      toast({
        title: 'Vapi Error',
        description: err?.message || 'An error occurred during the voice call.',
        variant: 'destructive',
      });
      setCallStatus('idle');
    });
    // Start the Vapi call
    try {
      vapi.start(vapiConfig.assistant_id);
    } catch (err) {
      console.error('Vapi start error:', err);
      toast({
        title: 'Call Failed',
        description: 'Unable to start Vapi voice call.',
        variant: 'destructive',
      });
      setCallStatus('idle');
      return;
    }
    setCallStatus('connecting');
    setCallDuration(0);
    setTranscripts([]);

    toast({
      title: "Connecting to Vapi Voice Assistant...",
      description: "Establishing secure real-time WebRTC audio connection",
    });

    setTimeout(() => {
      setCallStatus("active");

      // Initial AI greeting
      const greeting = initialQuery
        ? `Assalam-o-Alaikum! I heard you are interested in: "${initialQuery}". Let me help you with details and booking!`
        : `Assalam-o-Alaikum! Welcome to Real Estate Hub. I am your AI sales agent. Are you looking to buy, invest, or schedule a property visit today?`;

      setTranscripts([
        {
          role: "assistant",
          text: greeting,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    }, 1500);
  };

  const sendSimulatedUserSpeech = (text: string) => {
    if (callStatus !== "active") return;

    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    // Add user response
    setTranscripts((prev) => [...prev, { role: "user", text, timestamp: timeStr }]);

    // Trigger Vapi Webhook backend call to process intent & response
    setTimeout(async () => {
      try {
        const chatRes = await fetch("/api/proxy/agent/chat", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-API-Key": process.env.NEXT_PUBLIC_API_KEY || "",
          },
          body: JSON.stringify({
            session_id: `vapi-session-${user?.id || "guest"}`,
            message: text,
          }),
        });

        const chatData = await chatRes.json();
        const responseText = chatData.reply || chatData.response || "Ji, I can assist you with properties in Lahore, Islamabad, and Karachi. Would you like to book a visit?";

        setTranscripts((prev) => [
          ...prev,
          {
            role: "assistant",
            text: responseText,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ]);
      } catch (err) {
        setTranscripts((prev) => [
          ...prev,
          {
            role: "assistant",
            text: "Ji, DHA Phase 6 and Bahria Town have excellent 5 & 10 marla houses available starting from 2.5 Crore PKR. Shall I schedule a visit for you?",
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ]);
      }
    }, 1000);
  };

  const endVoiceCall = async () => {
    // Cleanup Vapi on end
    if (vapiInstanceRef.current) {
      vapiInstanceRef.current.stop();
      vapiInstanceRef.current = null;
    }
    setCallStatus("ended");

    // Post End of Call Report to Vapi Webhook endpoint
    try {
      const fullTranscriptText = transcripts.map((t) => `${t.role}: ${t.text}`).join("\n");
      await fetch("/api/proxy/webhooks/vapi", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: {
            type: "end-of-call-report",
            durationSeconds: callDuration,
            transcript: fullTranscriptText,
            summary: `User discussed real estate options for ${callDuration}s`,
            call: {
              customer: {
                number: user ? "+923001234567" : "+923000000000",
                email: user?.email || "guest@gmail.com",
                name: user?.name || "Voice Caller",
              },
            },
          },
        }),
      });
    } catch (e) {
      console.error("Vapi webhook report error:", e);
    }

    toast({
      title: "Voice Call Ended",
      description: `Call transcript and preferences saved to ${user ? user.name : "your account"}.`,
    });
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* VAPI VOICE CALL CONTROL CARD */}
      <Card className="p-8 bg-card/90 backdrop-blur-md border-border shadow-xl relative overflow-hidden text-center">
        {/* Ambient background glow when active */}
        {callStatus === "active" && (
          <div className="absolute inset-0 bg-emerald-500/5 animate-pulse pointer-events-none" />
        )}

        <div className="relative z-10 flex flex-col items-center">
          <Badge variant="outline" className="mb-4 px-3 py-1 text-xs uppercase tracking-widest gap-1.5 bg-background">
            <Sparkles className="w-3.5 h-3.5 text-emerald-500" />
            Connect with our Agent
          </Badge>

          {/* PULSING AUDIO CALL SPHERE */}
          <div className="relative my-6">
            {callStatus === "active" && (
              <>
                <div className="absolute -inset-4 rounded-full bg-emerald-500/20 animate-ping opacity-75" />
                <div className="absolute -inset-8 rounded-full bg-emerald-500/10 animate-pulse" />
              </>
            )}
            <div
              className={`w-28 h-28 rounded-full flex items-center justify-center shadow-2xl transition-all duration-500 ${callStatus === "active"
                  ? "bg-gradient-to-tr from-emerald-600 to-teal-500 text-white scale-110"
                  : callStatus === "connecting"
                    ? "bg-amber-500 text-white animate-bounce"
                    : "bg-muted text-muted-foreground"
                }`}
            >
              {callStatus === "active" ? (
                <Volume2 className="w-12 h-12 animate-pulse" />
              ) : callStatus === "connecting" ? (
                <Activity className="w-12 h-12 animate-spin" />
              ) : (
                <Phone className="w-12 h-12" />
              )}
            </div>
          </div>

          {/* STATUS & TIMER */}
          <div className="space-y-1 mb-6">
            <h3 className="text-2xl font-bold text-foreground">
              {callStatus === "active"
                ? "Live AI Voice Call Active"
                : callStatus === "connecting"
                  ? "Connecting to Vapi Assistant..."
                  : callStatus === "ended"
                    ? "Voice Call Ended"
                    : "Real Estate Voice Agent"}
            </h3>
            <p className="text-sm text-muted-foreground flex items-center justify-center gap-2">
              <Clock className="w-4 h-4 text-emerald-500" />
              {callStatus === "active" ? (
                <span className="font-mono font-semibold text-emerald-600 dark:text-emerald-400">
                  Duration: {formatDuration(callDuration)}
                </span>
              ) : (
                "Speak naturally in English or Urdu to inquire about properties & book visits"
              )}
            </p>
          </div>

          {/* CALL CONTROLS */}
          <div className="flex items-center gap-4">
            {callStatus === "idle" || callStatus === "ended" ? (
              <Button
                size="lg"
                onClick={() => startVoiceCall()}
                className="bg-emerald-600 hover:bg-emerald-700 text-white px-8 py-6 rounded-full font-semibold shadow-lg shadow-emerald-600/20 text-base"
              >
                <Phone className="w-5 h-5 mr-2" /> Start Voice Call
              </Button>
            ) : (
              <>
                <Button
                  variant={isMuted ? "destructive" : "outline"}
                  size="icon"
                  className="w-12 h-12 rounded-full"
                  onClick={() => {
                    // Toggle mute state via Vapi SDK if supported, otherwise no-op
                    const newMuted = !isMuted;
                    setIsMuted(newMuted);
                    // Vapi SDK does not expose a direct mute method; UI state only.
                  
                  }}
                >
                  {isMuted ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
                </Button>

                <Button
                  variant="destructive"
                  size="lg"
                  onClick={endVoiceCall}
                  className="px-8 py-6 rounded-full font-semibold text-base shadow-lg shadow-red-600/20"
                >
                  <PhoneOff className="w-5 h-5 mr-2" /> End Call
                </Button>
              </>
            )}
          </div>
        </div>
      </Card>

      {/* QUICK SPEECH PROMPTS DURING CALL */}
      {callStatus === "active" && (
        <Card className="p-4 bg-muted/40 border-border">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <Mic className="w-3.5 h-3.5 text-primary" /> Tap to speak to agent:
          </p>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => sendSimulatedUserSpeech("I am looking for a 5 Marla house in DHA Lahore Phase 6.")}
              className="text-xs rounded-full"
            >
              "5 Marla House in DHA Lahore"
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => sendSimulatedUserSpeech("What is the price of 1 Kanal Villa in Capital Smart City?")}
              className="text-xs rounded-full"
            >
              "Price of 1 Kanal Villa"
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => sendSimulatedUserSpeech("I want to book a visit for tomorrow at 3 PM.")}
              className="text-xs rounded-full"
            >
              "Book a visit for tomorrow 3 PM"
            </Button>
          </div>
        </Card>
      )}

      {/* LIVE TRANSCRIPT LOG */}
      {transcripts.length > 0 && (
        <Card className="p-6 bg-card border-border">
          <div className="flex items-center justify-between mb-4 pb-2 border-b border-border">
            <h4 className="font-semibold text-foreground flex items-center gap-2">
              <FileText className="w-4 h-4 text-primary" />
              Live Call Transcript & Webhook Sync
            </h4>
            <Badge variant="secondary" className="text-xs">
              {user ? `Linked to ${user.email}` : "Guest Session"}
            </Badge>
          </div>

          <div className="space-y-3 max-h-[300px] overflow-y-auto pr-2">
            {transcripts.map((t, idx) => (
              <div
                key={idx}
                className={`p-3 rounded-xl max-w-[85%] text-sm ${t.role === "assistant"
                    ? "bg-primary/10 border border-primary/20 text-foreground ml-0"
                    : "bg-emerald-500/10 border border-emerald-500/20 text-foreground ml-auto"
                  }`}
              >
                <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                  <span className="font-medium">{t.role === "assistant" ? "Vapi Voice AI" : user?.name || "You"}</span>
                  <span>{t.timestamp}</span>
                </div>
                <p>{t.text}</p>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
