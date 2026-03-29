import React from "react";

export default function SystemStatus({ status }) {
  const config = {
    idle: {
      label: "Idle",
      dotClass: "bg-slate-500",
      bgClass: "bg-slate-100/80 border-slate-300/70 dark:bg-slate-800/70 dark:border-slate-700",
      textClass: "text-slate-700 dark:text-slate-300",
    },
    processing: {
      label: "Processing",
      dotClass: "bg-cyan-400 animate-pulse",
      bgClass: "bg-cyan-100/70 border-cyan-300/80 dark:bg-cyan-950/50 dark:border-cyan-800",
      textClass: "text-cyan-800 dark:text-cyan-300",
    },
    ready: {
      label: "Ready",
      dotClass: "bg-emerald-400",
      bgClass: "bg-emerald-100/80 border-emerald-300/80 dark:bg-emerald-950/50 dark:border-emerald-800",
      textClass: "text-emerald-800 dark:text-emerald-300",
    },
  };

  const current = config[status] || config.idle;

  return (
    <div
      className={`
        status-pill
        ${current.bgClass}
        transition-all duration-300
      `}
    >
      <div
        className={`
          h-2.5 w-2.5 rounded-full
          ${current.dotClass}
        `}
      />
      <span className={`${current.textClass}`}>
        {current.label}
      </span>
    </div>
  );
}
