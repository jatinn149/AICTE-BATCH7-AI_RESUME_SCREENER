import React from "react";

export default function SystemStatus({ status }) {
  const config = {
    idle: {
      label: "Idle",
      color: "bg-slate-400",
      glow: "",
    },
    processing: {
      label: "Processing",
      color: "bg-indigo-400",
      glow: "shadow-[0_0_12px_rgba(99,102,241,0.9)]",
    },
    ready: {
      label: "Ready",
      color: "bg-emerald-400",
      glow: "shadow-[0_0_12px_rgba(52,211,153,0.9)]",
    },
  };

  const current = config[status] || config.idle;

  return (
    <div className="flex items-center gap-2 text-sm">
      <span
        className={`
          h-2.5 w-2.5 rounded-full
          ${current.color}
          transition-all duration-500
          ${current.glow}
        `}
      />
      <span className="text-slate-600 dark:text-slate-400">
        System:{" "}
        <span className="font-medium text-slate-900 dark:text-white">
          {current.label}
        </span>
      </span>
    </div>
  );
}
