import { SignInButton, SignUpButton } from "@clerk/react";

// Public marketing page. No auth required to view — Clerk only fires when a
// visitor clicks into the playground (modal sign-up) or "Sign in".
export default function Landing() {
  return (
    <div className="landing">
      <header className="lhead">
        <span className="logo">Pixel</span>
        <SignInButton mode="modal">
          <button className="ghost">Sign in</button>
        </SignInButton>
      </header>

      <section className="hero">
        <h1>See where attention goes. Fix it. Prove the lift.</h1>
        <p className="lede">
          Upload campaign creative and Pixel predicts where human eyes land, then
          a team of agents edits the image to pull attention onto your brand —
          and shows you the before/after attention score to prove it worked.
        </p>
        <SignUpButton mode="modal">
          <button className="primary cta">Open the playground</button>
        </SignUpButton>
      </section>

      <section className="demo">
        <div className="video-frame">
          <video controls poster="/demo-poster.png" preload="metadata">
            <source src="/demo.mp4" type="video/mp4" />
          </video>
          <div className="video-fallback">Demo video</div>
        </div>
      </section>

      <section className="steps">
        <div className="step">
          <span className="n">1</span>
          <h3>Upload</h3>
          <p>Drop in an ad or campaign image.</p>
        </div>
        <div className="step">
          <span className="n">2</span>
          <h3>Predict gaze</h3>
          <p>DeepGaze maps where eyes actually go.</p>
        </div>
        <div className="step">
          <span className="n">3</span>
          <h3>Optimize &amp; prove</h3>
          <p>Agents edit, then re-score the lift.</p>
        </div>
      </section>
    </div>
  );
}
