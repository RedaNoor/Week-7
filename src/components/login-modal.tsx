"use client";

import { useState } from "react";
import { useAuth } from "./auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ShieldCheck, UserCheck, LogIn, UserPlus, Sparkles, KeyRound } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

export function LoginModal({ isOpen, onOpenChange }: { isOpen: boolean; onOpenChange: (open: boolean) => void }) {
  const { login, register, user, logout } = useAuth();
  const { toast } = useToast();

  const [activeTab, setActiveTab] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState("user");
  const [loading, setLoading] = useState(false);

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email, password);
      toast({
        title: "Successfully logged in",
        description: `Welcome back!`,
      });
      onOpenChange(false);
    } catch (err: any) {
      toast({
        title: "Login failed",
        description: err.message || "Invalid credentials",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await register(email, password, name, role);
      toast({
        title: "Account Created",
        description: `Welcome to Real Estate Hub!`,
      });
      onOpenChange(false);
    } catch (err: any) {
      toast({
        title: "Registration failed",
        description: err.message || "Could not register account",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleQuickLogin = async (demoEmail: string, demoPass: string) => {
    setLoading(true);
    try {
      await login(demoEmail, demoPass);
      toast({
        title: "Logged in with Demo Account",
        description: `Signed in as ${demoEmail}`,
      });
      onOpenChange(false);
    } catch (err: any) {
      toast({
        title: "Demo login failed",
        description: err.message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px] bg-card border-border shadow-2xl">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold flex items-center gap-2">
            <KeyRound className="w-5 h-5 text-primary" />
            Account Authentication
          </DialogTitle>
          <DialogDescription>
            Log in to view your personal property appointments, voice call logs, and memory.
          </DialogDescription>
        </DialogHeader>

        {user ? (
          <div className="py-4 text-center space-y-4">
            <div className="p-4 bg-muted/50 rounded-lg flex items-center justify-between">
              <div className="text-left">
                <p className="font-semibold text-foreground">{user.name}</p>
                <p className="text-sm text-muted-foreground">{user.email}</p>
              </div>
              <span className={`px-2.5 py-1 text-xs rounded-full font-medium ${
                user.role === "admin" 
                  ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20"
                  : "bg-primary/10 text-primary border border-primary/20"
              }`}>
                {user.role.toUpperCase()}
              </span>
            </div>

            <Button
              variant="outline"
              onClick={() => {
                logout();
                toast({ title: "Logged out" });
                onOpenChange(false);
              }}
              className="w-full text-destructive hover:bg-destructive/10"
            >
              Sign Out
            </Button>
          </div>
        ) : (
          <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as any)} className="w-full">
            <TabsList className="grid w-full grid-cols-2 mb-4">
              <TabsTrigger value="login" className="flex items-center gap-1.5">
                <LogIn className="w-4 h-4" /> Log In
              </TabsTrigger>
              <TabsTrigger value="register" className="flex items-center gap-1.5">
                <UserPlus className="w-4 h-4" /> Register
              </TabsTrigger>
            </TabsList>

            {/* QUICK DEMO LOGINS */}
            <div className="mb-4 p-3 bg-muted/40 rounded-lg border border-border/50">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1">
                <Sparkles className="w-3.5 h-3.5 text-amber-500" /> One-Click Demo Access
              </p>
              <div className="grid grid-cols-2 gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  disabled={loading}
                  onClick={() => handleQuickLogin("client@gmail.com", "user123")}
                  className="text-xs justify-start h-9"
                >
                  <UserCheck className="w-3.5 h-3.5 mr-1.5 text-blue-500" />
                  Client Demo
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  disabled={loading}
                  onClick={() => handleQuickLogin("admin@realestate.pk", "admin123")}
                  className="text-xs justify-start h-9"
                >
                  <ShieldCheck className="w-3.5 h-3.5 mr-1.5 text-amber-500" />
                  Admin Demo
                </Button>
              </div>
            </div>

            <TabsContent value="login">
              <form onSubmit={handleLoginSubmit} className="space-y-4">
                <div className="space-y-1.5">
                  <Label htmlFor="login-email">Email Address</Label>
                  <Input
                    id="login-email"
                    type="email"
                    placeholder="client@gmail.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="login-password">Password</Label>
                  <Input
                    id="login-password"
                    type="password"
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                </div>
                <Button type="submit" className="w-full mt-2" disabled={loading}>
                  {loading ? "Signing in..." : "Sign In"}
                </Button>
              </form>
            </TabsContent>

            <TabsContent value="register">
              <form onSubmit={handleRegisterSubmit} className="space-y-4">
                <div className="space-y-1.5">
                  <Label htmlFor="reg-name">Full Name</Label>
                  <Input
                    id="reg-name"
                    placeholder="Your Name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="reg-email">Email Address</Label>
                  <Input
                    id="reg-email"
                    type="email"
                    placeholder="name@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="reg-password">Password</Label>
                  <Input
                    id="reg-password"
                    type="password"
                    placeholder="At least 4 characters"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                </div>
                <Button type="submit" className="w-full mt-2" disabled={loading}>
                  {loading ? "Creating Account..." : "Create Account"}
                </Button>
              </form>
            </TabsContent>
          </Tabs>
        )}
      </DialogContent>
    </Dialog>
  );
}
