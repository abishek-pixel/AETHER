import { Link, useRouterState, useNavigate } from "@tanstack/react-router";
import {
  LayoutDashboard, Plus, FolderOpen, Users, BarChart3, Settings,
  Search, LogOut, User, Loader2,
} from "lucide-react";
import { Logo } from "@/components/common/Logo";
import { cn } from "@/lib/utils";
import { useResearchStore } from "@/store/research";
import { useAuthStore } from "@/store/auth";
import { Button } from "@/components/ui/button";

const NAV_ITEMS = [
  { to: "/dashboard",     label: "Dashboard",      icon: LayoutDashboard },
  { to: "/saved-reports", label: "Saved Reports",  icon: FolderOpen },
  { to: "/analytics",     label: "Analytics",      icon: BarChart3 },
  { to: "/settings",      label: "Settings",       icon: Settings },
  { to: "/dashboard",     label: "Team Workspace", icon: Users, soon: true },
];

export function Sidebar() {
  const path = useRouterState({ select: (s) => s.location.pathname });
  const sessions = useResearchStore((s) => s.sessions);
  const isFetching = useResearchStore((s) => s.isFetchingHistory);
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate({ to: "/login" });
  };

  // Only show completed sessions in the sidebar (status === "done")
  const recentSessions = sessions.filter((s) => s.status === "done").slice(0, 10);

  return (
    <aside className="hidden md:flex w-64 shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground">
      {/* Logo */}
      <div className="p-4">
        <Link to="/"><Logo /></Link>
      </div>

      {/* New Research CTA */}
      <div className="px-3 mb-2">
        <Button asChild className="w-full justify-start bg-primary/10 border border-primary/30 text-foreground hover:bg-primary/20" variant="ghost" size="sm">
          <Link to="/dashboard"><Plus className="mr-2 h-4 w-4 text-primary" /> New Research</Link>
        </Button>
      </div>

      {/* Nav */}
      <nav className="px-3 space-y-1">
        {NAV_ITEMS.map((it) => {
          const active = path === it.to && it.to !== "/dashboard" || (it.to === "/dashboard" && path === "/dashboard");
          return (
            <Link
              key={it.label}
              to={it.to}
              className={cn(
                "group flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "hover:bg-sidebar-accent/60 text-muted-foreground hover:text-foreground",
              )}
            >
              <it.icon className="h-4 w-4" />
              <span className="flex-1">{it.label}</span>
              {it.soon && <span className="text-[10px] rounded bg-muted px-1.5 py-0.5 text-muted-foreground">soon</span>}
            </Link>
          );
        })}
      </nav>

      {/* Recent Sessions */}
      <div className="mt-5 px-4 flex items-center gap-2 text-xs uppercase tracking-wider text-muted-foreground">
        <span>Recent sessions</span>
        {isFetching && <Loader2 className="h-3 w-3 animate-spin" />}
      </div>

      <div className="mt-1 flex-1 overflow-y-auto px-3 space-y-0.5">
        {recentSessions.length === 0 && !isFetching && (
          <p className="px-2 py-3 text-xs text-muted-foreground italic">
            {user ? "No sessions yet — start a research!" : "Log in to see your history."}
          </p>
        )}
        {recentSessions.map((s) => (
          <Link
            key={s.id}
            to="/research/$sessionId"
            params={{ sessionId: s.id }}
            className={cn(
              "flex items-start gap-2 rounded-md px-2 py-2 text-xs transition-colors",
              path === `/research/${s.id}`
                ? "bg-sidebar-accent text-foreground"
                : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground",
            )}
          >
            <Search className="mt-0.5 h-3 w-3 shrink-0 opacity-60" />
            <span className="line-clamp-2">{s.query}</span>
          </Link>
        ))}
      </div>

      {/* User / Auth footer */}
      <div className="p-3 border-t border-sidebar-border">
        {user ? (
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/20 text-primary-glow text-xs font-semibold">
                {user.name.charAt(0).toUpperCase()}
              </div>
              <div className="min-w-0">
                <div className="text-xs font-medium truncate">{user.name}</div>
                <div className="text-[10px] text-muted-foreground capitalize">{user.plan} plan</div>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="shrink-0 rounded p-1.5 text-muted-foreground hover:bg-sidebar-accent hover:text-foreground"
              title="Log out"
            >
              <LogOut className="h-3.5 w-3.5" />
            </button>
          </div>
        ) : (
          <Button asChild variant="secondary" size="sm" className="w-full justify-start">
            <Link to="/login"><User className="mr-2 h-4 w-4" /> Sign in</Link>
          </Button>
        )}
      </div>
    </aside>
  );
}
