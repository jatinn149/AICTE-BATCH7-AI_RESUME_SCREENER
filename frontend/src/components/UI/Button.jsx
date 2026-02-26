import React from "react";

export default function Button({ children, disabled, onClick }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`
        inline-flex items-center justify-center
        rounded-xl
        px-6 py-2.5
        text-sm font-semibold
        transition-all duration-300
        ${
          disabled
            ? "bg-slate-700 text-slate-400 cursor-not-allowed"
            : `
              bg-gradient-to-r from-indigo-500 to-cyan-500
              text-white
              hover:from-indigo-600 hover:to-cyan-600
              shadow-[0_0_18px_rgba(99,102,241,0.35)]
              hover:shadow-[0_0_26px_rgba(99,102,241,0.55)]
              active:scale-[0.97]
            `
        }
      `}
    >
      {children}
    </button>
  );
}
