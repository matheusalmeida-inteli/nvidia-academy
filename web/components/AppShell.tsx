"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Radar,
  Search,
  GitBranch,
  HeartHandshake,
  Settings,
  ExternalLink,
} from "lucide-react";

const NAV = [
  {
    label: "Análise",
    href: "/",
    icon: Search,
    description: "Consultar e analisar startups",
  },
  {
    label: "Pipeline",
    href: "/pipeline",
    icon: GitBranch,
    description: "Candidatos Inception",
  },
  {
    label: "Nutrição",
    href: "/nurture",
    icon: HeartHandshake,
    description: "Gestão de relacionamento",
  },
];

function NvidiaLogo() {
  return (
    <svg width="28" height="28" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M24 4L44 12V36L24 44L4 36V12L24 4Z"
        fill="#1a1a2e"
        stroke="#76b900"
        strokeWidth="1.5"
      />
      <path
        d="M24 4L44 12L24 20L4 12L24 4Z"
        fill="#76b900"
        opacity="0.9"
      />
      <path
        d="M24 20L44 12V36L24 44V20Z"
        fill="#76b900"
        opacity="0.4"
      />
      <path
        d="M24 20L4 12V36L24 44V20Z"
        fill="#76b900"
        opacity="0.7"
      />
    </svg>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-[220px] shrink-0 flex flex-col border-r border-border-subtle bg-bg-surface">
        {/* Logo */}
        <div className="px-5 py-5 border-b border-border-subtle">
          <div className="flex items-center gap-2.5">
            <NvidiaLogo />
            <div>
              <p className="text-sm font-semibold text-text-primary leading-none">
                NVIDIA Radar
              </p>
              <p className="text-2xs text-text-tertiary mt-0.5">
                Inception Brazil
              </p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-0.5">
          <p className="text-2xs font-medium text-text-tertiary uppercase tracking-widest px-2 mb-3">
            Menu
          </p>
          {NAV.map(({ label, href, icon: Icon, description }) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-all duration-100 group ${
                  active
                    ? "bg-accent-green-dim text-accent-green border border-accent-green/20"
                    : "text-text-secondary hover:text-text-primary hover:bg-bg-hover"
                }`}
              >
                <Icon
                  size={16}
                  strokeWidth={active ? 2.5 : 2}
                  className={active ? "text-accent-green" : "text-text-tertiary group-hover:text-text-secondary"}
                />
                <span>{label}</span>
                {active && (
                  <span className="ml-auto w-1.5 h-1.5 rounded-full bg-accent-green shrink-0" />
                )}
              </Link>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="px-3 py-4 border-t border-border-subtle space-y-0.5">
          <a
            href="https://www.nvidia.com/pt-br/geforce/"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-2 px-3 py-2 rounded-md text-xs text-text-tertiary hover:text-text-secondary hover:bg-bg-hover transition-colors"
          >
            <ExternalLink size={13} strokeWidth={2} />
            NVIDIA Inception
          </a>
          <div className="flex items-center gap-2 px-3 py-2">
            <Settings size={13} strokeWidth={2} className="text-text-tertiary" />
            <span className="text-xs text-text-tertiary">v2.0.0</span>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        {children}
      </main>
    </div>
  );
}
