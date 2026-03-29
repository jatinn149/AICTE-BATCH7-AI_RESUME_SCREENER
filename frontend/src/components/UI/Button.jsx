import React from "react";

export default function Button({
  children,
  disabled,
  onClick,
  variant = "primary",
  size = "md",
  className = "",
  type = "button",
}) {
  const baseClasses =
    "inline-flex items-center justify-center gap-2 rounded-xl border text-sm font-semibold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-offset-2 dark:focus:ring-offset-slate-950 active:scale-[0.99]";

  const variants = {
    primary:
      "border-transparent bg-brand-600 text-white shadow-soft hover:bg-brand-700 focus:ring-brand-500",
    secondary:
      "border-transparent bg-teal-600 text-white shadow-soft hover:bg-teal-500 focus:ring-teal-500",
    ghost:
      "bg-white/70 text-slate-700 border-slate-300/70 hover:bg-white dark:bg-slate-800/80 dark:text-slate-200 dark:border-slate-700",
    danger:
      "border-transparent bg-red-600 text-white shadow-soft hover:bg-red-700 focus:ring-red-500",
    success:
      "border-transparent bg-emerald-600 text-white shadow-soft hover:bg-emerald-700 focus:ring-emerald-500",
  };

  const sizes = {
    sm: "h-9 px-3",
    md: "h-10 px-4",
    lg: "h-12 px-6 text-base",
  };

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`${baseClasses} ${variants[variant]} ${sizes[size]} ${className}`}
    >
      {children}
    </button>
  );
}
