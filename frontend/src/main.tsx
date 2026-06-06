import { ClerkProvider, ClerkLoaded, ClerkLoading, Show } from "@clerk/react";
import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import Landing from "./Landing";
import "./index.css";

const publishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;
if (!publishableKey) {
  throw new Error("Missing VITE_CLERK_PUBLISHABLE_KEY in .env.local");
}

// Public landing for signed-out visitors; the playground mounts only once
// signed in. Auth fires from the landing's modal buttons, not on load.
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
    <ClerkProvider publishableKey={publishableKey} afterSignOutUrl="/">
      <Gate />
    </ClerkProvider>
  </React.StrictMode>
);
