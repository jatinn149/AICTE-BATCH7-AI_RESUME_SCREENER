import React from "react";

export default function Card({ title, subtitle, children }) {
  return (
    <div
      className="
        relative
        rounded-2xl
        bg-white/90 dark:bg-slate-900/90
        backdrop-blur-xl
        border border-slate-200 dark:border-white/10
        shadow-[0_0_0_1px_rgba(255,255,255,0.02),0_20px_40px_rgba(0,0,0,0.6)]
        transition-shadow
        hover:shadow-[0_25px_50px_rgba(0,0,0,0.8)]
      "
    >
      <div className="p-8 space-y-6">
        {(title || subtitle) && (
          <div className="space-y-1">
            {title && (
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                {title}
              </h3>
            )}
            {subtitle && (
              <p className="text-sm text-slate-600 dark:text-slate-400">
                {subtitle}
              </p>
            )}
          </div>
        )}

        {children}
      </div>
    </div>
  );
}
