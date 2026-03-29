import React from "react";

export default function Card({
  title,
  subtitle,
  children,
  icon = null,
  step = null,
  className = "",
}) {
  return (
    <section className={`card-premium group stagger-in ${className}`}>
      <div className="pointer-events-none absolute inset-x-8 top-0 h-px brand-divider" />

      {(title || subtitle) && (
        <div className="mb-6 border-b border-slate-200/80 pb-5 dark:border-slate-700/70">
          <div className="flex items-start gap-4 md:gap-5">
            {icon && (
              <div className="mt-1 flex h-11 w-11 items-center justify-center rounded-xl border border-slate-200/80 bg-white/85 text-xl shadow-sm dark:border-slate-700 dark:bg-slate-900/70">
                {icon}
              </div>
            )}

            <div className="flex-1">
              {step && <p className="section-kicker mb-2">Step {step}</p>}

              {title && (
                <h3 className="font-display text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-50">
                  {title}
                </h3>
              )}

              {subtitle && (
                <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-600 dark:text-slate-300">
                  {subtitle}
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="space-y-6">{children}</div>
    </section>
  );
}
