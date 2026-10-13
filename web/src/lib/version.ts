import * as React from "react";
import { toast } from "sonner";


/** Reload the app when a new build is installed, but never in the middle of typing or with a dialog open. */
export function useVersionReload() {
  React.useEffect(() => {
    if (import.meta.env.DEV) return;
    let told = false;
    const t = setInterval(async () => {
      try {
        const r = await fetch("/static/ui/version.json", { cache: "no-store" }); const j = await r.json();
        if (!j.build || j.build === __BUILD_ID__) return;
        const a = document.activeElement as HTMLElement | null;
        const busy = !!document.querySelector("[role=dialog]") || (a && /INPUT|TEXTAREA|SELECT/.test(a.tagName));
        if (!busy) location.reload();
        else if (!told) { told = true; toast("Homunculus was updated: it reloads when you are done here."); }
      } catch { /* server restarting */ }
    }, 15000);
    return () => clearInterval(t);
  }, []);
}
