import {ClerkProvider, ClerkLoaded, ClerkLoading, Show, SignUp} from "@clerk/react";
import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

const publishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;
if (!publishableKey) {
  throw new Error("Missing VITE_CLERK_PUBLISHABLE_KEY in .env.local");
}

// Hard auth gate: the app only mounts for signed-in users. Everyone else
// gets the sign-up form immediately and cannot reach the tool.
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
          <div className="gate">
            <div className="gate-intro">
              <h1>Pixel</h1>
              <p>See where attention goes · fix it · prove the lift.</p>
              <p className="gate-sub">Sign up to start optimizing your campaign creative.</p>
            </div>
            <SignUp routing="hash" />
          </div>
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