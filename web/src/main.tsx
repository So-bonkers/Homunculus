import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { HashRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { TooltipProvider } from "@/components/ui";
import App from "./App";
import "./index.css";

const qc = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: true, retry: 1, staleTime: 1500 } },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={qc}>
      <TooltipProvider>
        <HashRouter>
          <App />
        </HashRouter>
        <Toaster theme="dark" position="bottom-right" toastOptions={{ className: "!bg-overlay !border-line-strong !text-ink" }} />
      </TooltipProvider>
    </QueryClientProvider>
  </StrictMode>,
);
