"use client"

import {
  CircleCheckIcon,
  InfoIcon,
  Loader2Icon,
  OctagonXIcon,
  TriangleAlertIcon,
} from "lucide-react"
import { Toaster as Sonner, type ToasterProps } from "sonner"

// COMPONENT_INVENTORY §4: bottom-right (bottom-centre below 640 px), max 3 visible, 5 s, close
// button. Light theme only in v1 (DESIGN_SYSTEM §1), so no theme provider is involved.
const Toaster = ({ ...props }: ToasterProps) => {
  return (
    <Sonner
      theme="light"
      position="bottom-right"
      visibleToasts={3}
      duration={5000}
      closeButton
      className="toaster group"
      icons={{
        success: <CircleCheckIcon className="size-4 text-tone-success-fg" />,
        info: <InfoIcon className="size-4 text-tone-info-fg" />,
        warning: <TriangleAlertIcon className="size-4 text-tone-warning-fg" />,
        error: <OctagonXIcon className="size-4 text-tone-danger-fg" />,
        loading: <Loader2Icon className="size-4 animate-spin" />,
      }}
      style={
        {
          "--normal-bg": "var(--popover)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--border)",
          "--border-radius": "8px",
          zIndex: "var(--z-toast)",
        } as React.CSSProperties
      }
      {...props}
    />
  )
}

export { Toaster }
