import { ClerkProvider } from "@clerk/react";
import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

// The playground IS the homescreen for everyone. Auth is optional: with a Clerk key
// the header shows "Log in" / your profile (and you can save projects); without a key
// the app still boots fully. No separate marketing/landing gate.
const publishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {publishableKey ? (
      <ClerkProvider publishableKey={publishableKey} afterSignOutUrl="/">
        <App />
      </ClerkProvider>
    ) : (
      <App />
    )}
  </React.StrictMode>
);
