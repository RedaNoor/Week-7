"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Toaster } from "@/components/ui/toaster";
import { useToast } from "@/hooks/use-toast";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { AuthProvider, useAuth } from "@/components/auth-context";
import { LoginModal } from "@/components/login-modal";
import { VoiceCallTab } from "@/components/voice-call-tab";
import {
  Building2,
  Bed,
  MapPin,
  Tag,
  Send,
  MessageSquare,
  Bot,
  User,
  Calendar,
  Search,
  TrendingUp,
  Mail,
  CheckCircle2,
  Clock,
  Sparkles,
  LogIn,
  UserCheck,
  ShieldCheck,
  PhoneCall,
  Volume2,
  BarChart3,
  ExternalLink,
} from "lucide-react";

// ============================================================================
// Types
// ============================================================================
interface Property {
  property_id: string;
  name: string;
  developer: string;
  city: string;
  area: string;
  type: string;
  bedrooms: number;
  price: number;
  status: string;
  purpose: string;
  brochure?: string;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  intent?: string;
  recommendations?: Property[];
  learned_context_used?: boolean;
  timestamp: string;
}

interface AgentStats {
  corpus_size: number;
  trained: boolean;
  n_clusters: number;
  intents: string[];
  outcomes: string[];
}

interface TopicSummary {
  cluster_id: number;
  size: number;
  top_terms: string[];
  avg_success_score: number;
  samples: { user_query: string; intent: string; outcome: string }[];
}

interface Appointment {
  id?: string;
  appointment_id?: string;
  client_name: string;
  client_phone?: string;
  property_id?: string;
  property_title: string;
  scheduled_at: string;
  status: string;
  employee_email?: string;
}

// ============================================================================
// API helpers — all requests go through the Next.js API proxy route
// ============================================================================
const BACKEND_PREFIX = "/api/proxy";

async function api<T>(
  path: string,
  options?: RequestInit & { query?: Record<string, string> }
): Promise<T> {
  const query = options?.query || {};
  const search = Object.keys(query).length
    ? "?" + new URLSearchParams(query).toString()
    : "";
  const token = typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;

  const reqHeaders: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const apiKey = process.env.NEXT_PUBLIC_API_KEY;
  if (apiKey) {
    reqHeaders["X-API-Key"] = apiKey.trim();
  }
  if (token) {
    reqHeaders["Authorization"] = `Bearer ${token}`;
  }
  if (options?.headers) {
    Object.assign(reqHeaders, options.headers);
  }

  const res = await fetch(`${BACKEND_PREFIX}${path}${search}`, {
    ...options,
    headers: reqHeaders,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json();
}

function formatPrice(p: number): string {
  if (p >= 10000000) return `PKR ${(p / 10000000).toFixed(2)} crore`;
  if (p >= 100000) return `PKR ${(p / 100000).toFixed(1)} lakh`;
  return `PKR ${p.toLocaleString()}`;
}

// ============================================================================
// Main page
// ============================================================================
export default function Home() {
  return (
    <AuthProvider>
      <HomeContent />
    </AuthProvider>
  );
}

function HomeContent() {
  const { user, logout } = useAuth();
  const { toast } = useToast();
  const [loginModalOpen, setLoginModalOpen] = useState(false);
  const [properties, setProperties] = useState<Property[]>([]);
  const [propertyTotal, setPropertyTotal] = useState(0);
  const [loadingProps, setLoadingProps] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [cityFilter, setCityFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");

  // AI chat state
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content:
        "Assalam-o-Alaikum! Main Zara hoon, aap ki kis tarah madad kar sakti hoon?",
      timestamp: new Date().toISOString(),
    },
  ]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [sessionId] = useState(`web_${Date.now()}`);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Appointment state
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [aptForm, setAptForm] = useState({
    client_name: "",
    client_phone: "",
    property_id: "",
    property_title: "",
    scheduled_at: "",
    employee_email: "",
  });

  // Memory state
  const [agentStats, setAgentStats] = useState<AgentStats | null>(null);
  const [topics, setTopics] = useState<TopicSummary[]>([]);

  // ----- load properties -----
  const loadProperties = useCallback(async () => {
    setLoadingProps(true);
    try {
      const data = await api<{ properties: Property[]; total: number }>("/properties");
      setProperties(data.properties || []);
      setPropertyTotal(data.total || data.properties?.length || 0);
    } catch (e) {
      toast({
        title: "Could not load properties",
        description: String(e),
        variant: "destructive",
      });
    } finally {
      setLoadingProps(false);
    }
  }, [toast]);

  // ----- load appointments -----
  const loadAppointments = useCallback(async () => {
    try {
      const data = await api<{ appointments: Appointment[] }>("/appointments");
      setAppointments(data.appointments || []);
    } catch (e) {
      // silently fail — appointments are best-effort
      console.error(e);
    }
  }, []);

  // ----- load agent memory stats -----
  const loadMemory = useCallback(async () => {
    try {
      const [stats, topicsResp] = await Promise.all([
        api<AgentStats>("/agent/memory/stats"),
        api<{ topics: TopicSummary[] }>("/agent/memory/topics"),
      ]);
      setAgentStats(stats);
      setTopics(topicsResp.topics || []);
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    loadProperties();
    loadAppointments();
    loadMemory();
  }, [loadProperties, loadAppointments, loadMemory]);

  // ----- chat scroll -----
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  // ----- chat submit -----
  const sendChat = async () => {
    if (!chatInput.trim() || chatLoading) return;
    const userMsg: ChatMessage = {
      role: "user",
      content: chatInput,
      timestamp: new Date().toISOString(),
    };
    setChatMessages((prev) => [...prev, userMsg]);
    setChatInput("");
    setChatLoading(true);
    try {
      const data = await api<{
        reply: string;
        intent?: string;
        recommendations?: Property[];
        learned_context_used?: boolean;
        next_step?: string;
        profile?: Record<string, unknown>;
      }>("/agent/chat", {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId, message: userMsg.content }),
      });
      const assistantMsg: ChatMessage = {
        role: "assistant",
        content: data.reply,
        intent: data.intent,
        recommendations: data.recommendations,
        learned_context_used: data.learned_context_used,
        timestamp: new Date().toISOString(),
      };
      setChatMessages((prev) => [...prev, assistantMsg]);
      // refresh memory stats after a turn so the user sees the learner grow
      setTimeout(loadMemory, 500);
    } catch (e) {
      setChatMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Sorry, I hit an error: ${e}. Please try again.`,
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  // ----- appointment submit -----
  const bookAppointment = async () => {
    if (
      !aptForm.client_name ||
      !aptForm.client_phone ||
      !aptForm.property_id ||
      !aptForm.scheduled_at
    ) {
      toast({
        title: "Missing fields",
        description: "Name, phone, property, and time are required.",
        variant: "destructive",
      });
      return;
    }
    try {
      const prop = properties.find((p) => p.property_id === aptForm.property_id);
      const iso = new Date(aptForm.scheduled_at).toISOString();
      const data = await api<{
        status: string;
        appointment: Appointment;
        email: { status: string; recipient: string };
      }>("/appointments", {
        method: "POST",
        body: JSON.stringify({
          ...aptForm,
          property_title: prop?.name || aptForm.property_title,
          scheduled_at: iso,
        }),
      });
      if (data.email?.status === "sent") {
        toast({
          title: "Appointment booked & email sent!",
          description: `Confirmation sent to ${data.email.recipient}. Check your inbox.`,
        });
      } else {
        toast({
          title: "Appointment booked",
          description: "But the email could not be sent. Check SMTP settings.",
        });
      }
      setAptForm({
        client_name: "",
        client_phone: "",
        property_id: "",
        property_title: "",
        scheduled_at: "",
        employee_email: "",
      });
      if (data.appointment) {
        setAppointments((prev) => {
          const aid = data.appointment.appointment_id || data.appointment.id;
          const filtered = prev.filter((a) => (a.appointment_id || a.id) !== aid);
          return [data.appointment, ...filtered];
        });
      }
      await loadAppointments();
    } catch (e) {
      toast({
        title: "Booking failed",
        description: String(e),
        variant: "destructive",
      });
    }
  };

  // ----- property filter -----
  const filteredProperties = properties.filter((p) => {
    if (cityFilter !== "all" && p.city !== cityFilter) return false;
    if (typeFilter !== "all" && p.type !== typeFilter) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return (
        p.name.toLowerCase().includes(q) ||
        p.area.toLowerCase().includes(q) ||
        p.developer.toLowerCase().includes(q)
      );
    }
    return true;
  });

  const cities = Array.from(new Set(properties.map((p) => p.city)));
  const types = Array.from(new Set(properties.map((p) => p.type)));

  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-br from-slate-50 via-white to-emerald-50/20">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b bg-white shadow-xs">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-md">
              <Building2 className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight">Real Estate Hub</h1>
              <p className="text-xs text-slate-500">Premier Property Advisory & Consultation</p>
            </div>
          </div>
          <div className="flex items-center gap-2.5">
            <a
              href={
                process.env.NEXT_PUBLIC_STREAMLIT_URL ||
                (typeof window !== "undefined"
                  ? `${window.location.origin}/api/py/docs`
                  : "/api/py/docs")
              }
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200 transition-colors shadow-sm"
              title="Open ML API Docs & Lead Scoring Dashboard"
            >
              <BarChart3 className="h-3.5 w-3.5 text-emerald-600" />
              <span className="hidden sm:inline">ML Dashboard</span>
              <ExternalLink className="h-3 w-3 opacity-60" />
            </a>
            {user ? (
              <div className="flex items-center gap-2">
                <Badge
                  variant="outline"
                  className={
                    user.role === "admin"
                      ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20 px-3 py-1 font-medium"
                      : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20 px-3 py-1 font-medium"
                  }
                >
                  {user.role === "admin" ? (
                    <ShieldCheck className="h-3.5 w-3.5 mr-1 text-amber-500" />
                  ) : (
                    <UserCheck className="h-3.5 w-3.5 mr-1 text-emerald-500" />
                  )}
                  {user.name} ({user.role.toUpperCase()})
                </Badge>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setLoginModalOpen(true)}
                  className="h-9"
                >
                  Account
                </Button>
              </div>
            ) : (
              <Button
                variant="default"
                size="sm"
                onClick={() => setLoginModalOpen(true)}
                className="bg-emerald-600 hover:bg-emerald-700 text-white font-medium shadow-md h-9"
              >
                <LogIn className="h-4 w-4 mr-1.5" /> Log In / Register
              </Button>
            )}
          </div>
        </div>
      </header>

      <LoginModal isOpen={loginModalOpen} onOpenChange={setLoginModalOpen} />

      {/* Hero */}
      <section className="relative overflow-hidden border-b">
        <div className="absolute inset-0 brand-gradient opacity-95" />
        <div className="absolute inset-0" style={{backgroundImage: "radial-gradient(ellipse at 70% 50%, rgba(255,255,255,0.08) 0%, transparent 60%)"}} />
        <div className="relative container mx-auto px-4 py-12 md:py-18">
          <div className="max-w-4xl">
            <Badge variant="secondary" className="mb-4 bg-white/20 text-white border-white/25 backdrop-blur-sm">
              <Sparkles className="h-3 w-3 mr-1.5" />
              AI-Powered Real Estate Consultancy
            </Badge>
            <h2 className="text-3xl md:text-5xl font-bold leading-tight mb-4 text-white">
              Find your dream home in Pakistan&apos;s most prestigious locations.
            </h2>
            <p className="text-white/85 text-base md:text-lg mb-7 max-w-2xl">
              Explore verified luxury houses, modern apartments, and prime plots across Lahore, Karachi, and Islamabad — with AI guidance in Roman Urdu or English.
            </p>
            <div className="flex flex-wrap gap-2 mb-8">
              {["DHA Lahore & Karachi", "Bahria Town", "Gulberg & Blue Area", "Verified Listings", "Site Visit Booking"].map((tag) => (
                <Badge key={tag} variant="secondary" className="bg-white/15 text-white border-white/20 hover:bg-white/25 transition-colors cursor-default">
                  {tag}
                </Badge>
              ))}
            </div>
            <div className="flex flex-wrap gap-6">
              {[
                { label: "Verified Properties", value: propertyTotal > 0 ? propertyTotal.toLocaleString() : "168,000+" },
                { label: "Cities Covered", value: "5" },
                { label: "Avg. Response Time", value: "< 2 min" },
              ].map((stat) => (
                <div key={stat.label} className="bg-white/10 backdrop-blur-sm rounded-xl px-5 py-3 border border-white/15">
                  <div className="text-2xl font-bold text-white">{stat.value}</div>
                  <div className="text-xs text-white/75">{stat.label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Main */}
      <main className="container mx-auto px-4 py-8 flex-1">
        <Tabs defaultValue="properties" className="w-full">
          <TabsList className="grid w-full grid-cols-2 sm:grid-cols-4 mb-6">
            <TabsTrigger value="properties" className="flex items-center gap-1">
              <Building2 className="h-4 w-4" />
              <span>Properties</span>
            </TabsTrigger>
            <TabsTrigger value="assistant" className="flex items-center gap-1">
              <MessageSquare className="h-4 w-4" />
              <span>Consultant Chat</span>
            </TabsTrigger>
            <TabsTrigger value="voice" className="flex items-center gap-1 text-emerald-600 font-semibold">
              <PhoneCall className="h-4 w-4" />
              <span>Voice Call</span>
            </TabsTrigger>
            <TabsTrigger value="appointments" className="flex items-center gap-1">
              <Calendar className="h-4 w-4" />
              <span>Book Visit</span>
            </TabsTrigger>
          </TabsList>

          {/* ============== Properties tab ============== */}
          <TabsContent value="properties" className="space-y-4">
            <div className="flex flex-wrap gap-2 items-center">
              <div className="relative flex-1 min-w-[200px]">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <Input
                  placeholder="Search by name, area, or developer..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9"
                />
              </div>
              <Select value={cityFilter} onValueChange={setCityFilter}>
                <SelectTrigger className="w-[140px]">
                  <SelectValue placeholder="City" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All cities</SelectItem>
                  {cities.map((c) => (
                    <SelectItem key={c} value={c}>
                      {c}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={typeFilter} onValueChange={setTypeFilter}>
                <SelectTrigger className="w-[140px]">
                  <SelectValue placeholder="Type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All types</SelectItem>
                  {types.map((t) => (
                    <SelectItem key={t} value={t}>
                      {t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="text-sm text-slate-500">
              Showing {filteredProperties.length} of {propertyTotal.toLocaleString()} properties
            </div>

            {loadingProps ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {Array.from({ length: 6 }).map((_, i) => (
                  <Card key={i} className="p-0 h-64 overflow-hidden">
                    <div className="h-36 shimmer" />
                    <div className="p-4 space-y-2">
                      <div className="h-3 shimmer rounded w-3/4" />
                      <div className="h-3 shimmer rounded w-1/2" />
                      <div className="h-5 shimmer rounded w-2/3" />
                    </div>
                  </Card>
                ))}
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredProperties.map((p, i) => (
                  <div key={p.property_id} className="animate-slide-up" style={{ animationDelay: `${Math.min(i * 40, 400)}ms` }}>
                    <PropertyCard property={p} />
                  </div>
                ))}
              </div>
            )}
          </TabsContent>

          {/* ============== Consultant Chat tab ============== */}
          <TabsContent value="assistant">
            <div className="w-full max-w-4xl mx-auto">
              <Card className="p-0 overflow-hidden flex flex-col h-[75vh] shadow-md border">
                <div className="bg-gradient-to-r from-emerald-600 to-teal-600 text-white px-5 py-3.5 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="h-9 w-9 rounded-xl bg-white/15 flex items-center justify-center">
                      <MessageSquare className="h-5 w-5 text-white" />
                    </div>
                    <div>
                      <div className="font-semibold text-base">Property Consultant (Zara)</div>
                      <div className="text-xs text-white/80">
                        Chat in Roman Urdu / Urdulish or English
                      </div>
                    </div>
                  </div>
                  <Badge variant="secondary" className="bg-white/15 text-white border-white/20 text-xs">
                    Verified Advisory
                  </Badge>
                </div>
                <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4 bg-slate-50">
                  {chatMessages.map((msg, i) => (
                    <ChatBubble key={i} msg={msg} />
                  ))}
                  {chatLoading && (
                    <div className="flex gap-3 items-center py-1">
                      <div className="h-8 w-8 rounded-full bg-gradient-to-br from-emerald-500 via-teal-500 to-emerald-600 flex items-center justify-center flex-shrink-0 shadow-sm">
                        <Sparkles className="h-4 w-4 text-white animate-pulse" />
                      </div>
                      <div className="inline-flex items-center gap-2.5 px-4 py-2.5 rounded-2xl bg-white border border-emerald-100 shadow-sm">
                        <div className="relative flex h-2 w-2">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                          <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                        </div>
                        <span className="text-sm font-medium bg-gradient-to-r from-emerald-700 via-teal-700 to-emerald-600 bg-clip-text text-transparent">
                          Connecting the dots for you...
                        </span>
                        <div className="flex gap-1 items-center ml-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-bounce [animation-delay:-0.3s]" />
                          <span className="w-1.5 h-1.5 rounded-full bg-teal-500 animate-bounce [animation-delay:-0.15s]" />
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-bounce" />
                        </div>
                      </div>
                    </div>
                  )}
                  <div ref={chatEndRef} />
                </div>
                <div className="border-t p-3.5 flex gap-2.5 bg-white">
                  <Input
                    placeholder="Sawal Roman Urdu ya English mein likhein (e.g. Lahore mein 5 marla ghar ka rate kya hai?)..."
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && sendChat()}
                    className="flex-1 h-11 text-sm"
                    disabled={chatLoading}
                  />
                  <Button
                    onClick={sendChat}
                    disabled={chatLoading || !chatInput.trim()}
                    className="bg-emerald-600 hover:bg-emerald-700 h-11 px-5"
                  >
                    <Send className="h-4 w-4" />
                  </Button>
                </div>
              </Card>
            </div>
          </TabsContent>

          {/* ============== Voice Call Tab (Vapi Webhook Integration) ============== */}
          <TabsContent value="voice">
            <VoiceCallTab />
          </TabsContent>

          {/* ============== Appointment tab ============== */}
          <TabsContent value="appointments">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card className="p-6">
                <h3 className="font-semibold text-lg mb-4 flex items-center gap-2">
                  <Calendar className="h-5 w-5 text-emerald-600" />
                  Book a Property Visit
                </h3>
                <div className="space-y-3">
                  <div>
                    <Label htmlFor="name">Your Name</Label>
                    <Input
                      id="name"
                      value={aptForm.client_name}
                      onChange={(e) =>
                        setAptForm({ ...aptForm, client_name: e.target.value })
                      }
                      placeholder="e.g. Ali Khan"
                    />
                  </div>
                  <div>
                    <Label htmlFor="phone">Phone</Label>
                    <Input
                      id="phone"
                      value={aptForm.client_phone}
                      onChange={(e) =>
                        setAptForm({ ...aptForm, client_phone: e.target.value })
                      }
                      placeholder="+92 300 1234567"
                    />
                  </div>
                  <div>
                    <Label htmlFor="prop">Property</Label>
                    <Select
                      value={aptForm.property_id}
                      onValueChange={(v) =>
                        setAptForm({ ...aptForm, property_id: v })
                      }
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select property" />
                      </SelectTrigger>
                      <SelectContent>
                        {properties.map((p) => (
                          <SelectItem key={p.property_id} value={p.property_id}>
                            {p.name} — {p.area}, {p.city}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="time">Visit Date & Time</Label>
                    <Input
                      id="time"
                      type="datetime-local"
                      value={aptForm.scheduled_at}
                      onChange={(e) =>
                        setAptForm({ ...aptForm, scheduled_at: e.target.value })
                      }
                    />
                  </div>
                  <div>
                    <Label htmlFor="email">Email (for confirmation)</Label>
                    <Input
                      id="email"
                      type="email"
                      value={aptForm.employee_email}
                      onChange={(e) =>
                        setAptForm({ ...aptForm, employee_email: e.target.value })
                      }
                      placeholder="you@example.com"
                    />
                  </div>
                  <Button
                    onClick={bookAppointment}
                    className="w-full bg-emerald-600 hover:bg-emerald-700"
                  >
                    <Mail className="h-4 w-4 mr-2" />
                    Book Visit & Send Confirmation
                  </Button>
                </div>
              </Card>

              <Card className="p-6">
                <h3 className="font-semibold text-lg mb-4 flex items-center gap-2">
                  <Clock className="h-5 w-5 text-emerald-600" />
                  Upcoming Appointments
                </h3>
                {appointments.length === 0 ? (
                  <div className="text-slate-500 text-sm py-12 text-center">
                    No appointments booked yet. Use the form to book your first visit.
                  </div>
                ) : (
                  <div className="space-y-3 max-h-[60vh] overflow-y-auto">
                    {appointments.map((a, idx) => (
                      <div
                        key={a.appointment_id || a.id || `apt_${idx}`}
                        className="p-3 rounded-lg border bg-white hover:bg-slate-50"
                      >
                        <div className="flex justify-between items-start mb-1">
                          <span className="font-medium">{a.client_name}</span>
                          <Badge
                            variant={
                              a.status === "confirmed"
                                ? "default"
                                : a.status === "cancelled"
                                  ? "destructive"
                                  : "secondary"
                            }
                            className="text-xs"
                          >
                            {a.status}
                          </Badge>
                        </div>
                        <div className="text-sm text-slate-600">{a.property_title}</div>
                        <div className="text-xs text-slate-500 mt-1 flex items-center gap-1">
                          <Calendar className="h-3 w-3" />
                          {a.scheduled_at ? new Date(a.scheduled_at).toLocaleString() : "Date TBA"}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            </div>
          </TabsContent>
        </Tabs>
      </main>

      {/* Footer */}
      <footer className="mt-auto border-t bg-slate-900 text-slate-300">
        <div className="container mx-auto px-4 py-6">
          <div className="flex flex-col md:flex-row justify-between items-center gap-3">
            <div className="flex items-center gap-2">
              <Building2 className="h-4 w-4 text-emerald-400" />
              <span className="text-sm font-medium">Real Estate Hub</span>
              <span className="text-xs text-slate-500">·</span>
              <span className="text-xs text-slate-500">
                Premier Real Estate Advisory &amp; Property Consultation
              </span>
            </div>
            <div className="text-xs text-slate-500">
              {propertyTotal.toLocaleString()} Verified Properties · Prime Locations · Pakistan
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

// ============================================================================
// Sub-components
// ============================================================================
// Colour palette for property cards
const CARD_GRADIENTS = [
  "from-emerald-500 via-teal-500 to-cyan-600",
  "from-teal-500 via-cyan-500 to-blue-500",
  "from-green-500 via-emerald-500 to-teal-500",
  "from-cyan-500 via-teal-500 to-emerald-500",
];

function PropertyCard({ property: p }: { property: Property }) {
  const [expanded, setExpanded] = useState(false);
  const gradIdx = Math.abs(p.property_id.charCodeAt(0) + p.property_id.charCodeAt(1)) % CARD_GRADIENTS.length;
  const grad = CARD_GRADIENTS[gradIdx];

  return (
    <Card className="overflow-hidden card-hover border border-slate-100 shadow-sm">
      {/* Card image / header */}
      <div className={`h-36 bg-gradient-to-br ${grad} relative overflow-hidden`}>
        {/* Subtle shine overlay */}
        <div className="absolute inset-0" style={{backgroundImage: "radial-gradient(ellipse at 30% 30%, rgba(255,255,255,0.15) 0%, transparent 60%)"}} />
        <div className="absolute top-2.5 right-2.5 flex gap-1.5">
          <Badge className="bg-white/90 text-slate-700 text-xs capitalize shadow-sm border-0">
            {p.status}
          </Badge>
        </div>
        <div className="absolute bottom-3 left-3 right-3 text-white">
          <div className="text-xs font-medium opacity-80 mb-0.5">{p.developer}</div>
          <div className="text-base font-bold leading-tight truncate">{p.name}</div>
        </div>
      </div>

      {/* Card body */}
      <div className="p-4 space-y-3">
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <MapPin className="h-3.5 w-3.5 text-emerald-500" />
            {p.area}, {p.city}
          </span>
          <span className="flex items-center gap-1.5">
            <Bed className="h-3.5 w-3.5 text-emerald-500" />
            {p.bedrooms} beds
          </span>
        </div>

        <div className="flex items-center gap-1.5">
          <Tag className="h-4 w-4 text-emerald-600" />
          <span className="text-lg font-bold gradient-text">{formatPrice(p.price)}</span>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant="secondary" className="text-xs bg-emerald-50 text-emerald-700 border-emerald-100">
            {p.type}
          </Badge>
          <Badge variant="outline" className="text-xs capitalize">
            {p.purpose.toLowerCase()}
          </Badge>
        </div>

        {p.brochure && (
          <>
            <Button
              variant="outline"
              size="sm"
              className="w-full text-xs h-8 border-emerald-200 text-emerald-700 hover:bg-emerald-50"
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? "Hide details" : "View brochure & details"}
            </Button>
            {expanded && (
              <div className="text-xs text-slate-600 max-h-40 overflow-y-auto bg-slate-50/80 p-3 rounded-lg border border-slate-100">
                {p.brochure.slice(0, 500)}
                {p.brochure.length > 500 && (
                  <span className="text-slate-400"> ...more</span>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </Card>
  );
}

function ChatBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === "user";
  return (
    <div className={`flex gap-2 ${isUser ? "justify-end" : "justify-start"}`}>
      {!isUser && (
        <div className="h-8 w-8 rounded-full bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center flex-shrink-0 shadow-sm">
          <Building2 className="h-4 w-4 text-white" />
        </div>
      )}
      <div
        className={`max-w-[80%] rounded-2xl p-3 text-sm ${isUser
          ? "bg-emerald-600 text-white"
          : "bg-white border text-slate-800 shadow-sm"
          }`}
      >
        <div className="whitespace-pre-wrap">{msg.content}</div>
      </div>
      {isUser && (
        <div className="h-8 w-8 rounded-full bg-slate-300 flex items-center justify-center flex-shrink-0">
          <User className="h-4 w-4 text-slate-600" />
        </div>
      )}
    </div>
  );
}

function StatBox({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: number | string;
}) {
  return (
    <div className="p-4 rounded-lg border bg-white">
      <div className="flex items-center gap-2 mb-1">{icon}</div>
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  );
}
