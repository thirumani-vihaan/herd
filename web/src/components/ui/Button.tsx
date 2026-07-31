import React from 'react'

export function Button({ children, onClick, variant = 'primary', className = '' }: any) {
  const base = "px-4 py-2 rounded-lg font-medium transition-all duration-200 active:scale-95"
  const variants = {
    primary: "bg-primary text-white hover:bg-blue-600 shadow-lg shadow-primary/20",
    outline: "border border-border bg-surface/50 hover:bg-border text-white"
  }
  return (
    <button className={`${base} ${(variants as any)[variant]} ${className}`} onClick={onClick}>
      {children}
    </button>
  )
}
