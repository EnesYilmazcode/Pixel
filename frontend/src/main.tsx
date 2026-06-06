import { ClerkProvider, ClerkLoaded, ClerkLoading, Show } from "@clerk/react";
import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import Landing from "./Landing";
import "./index.css";

// Auth is optional: with a Clerk key we show the public Landing → sign-in → playground.
// Without one (dev/demo), we skip auth and mount the playground directly so the app
// always boots. This matches .env.example's "app boots without it" note.
const publishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

function Gate() {
  return (
    <>
      <ClerkLoading>
        <div className="gate">
          <div className="gate-loading">Loading…</div>
        </div>
      </ClerkLoading>
      <ClerkLoaded>
        <Show when="signed-in">
          <App />
        </Show>
        <Show when="signed-out">
          <Landing />
        </Show>
      </ClerkLoaded>
    </>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {publishableKey ? (
      <ClerkProvider publishableKey={publishableKey} afterSignOutUrl="/">
        <Gate />
      </ClerkProvider>
    ) : (
      <App />
    )}
  </React.StrictMode>
);
