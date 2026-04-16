import React from "react";
import "../../styles/startpage/home.css";

const Home = () => {
  return (
    <section className="home" id="home">
      {/* ── Video Background ── */}
      <div className="home__video-wrap">
        {/*
          Replace the src below with your actual video path.
          Recommended: a looping abstract light/sphere or particle video.
          e.g. src="/src/assets/videos/hero-bg.mp4"
        */}
        <video
          className="home__video"
          src="/src/assets/videos/hero-bg.mp4"
          autoPlay
          loop
          muted
          playsInline
        />
        <div className="home__overlay" />
      </div>

      {/* ── Floating 3D Spheres (CSS) ── */}
      <div className="home__spheres" aria-hidden="true">
        <div className="sphere sphere--1" />
        <div className="sphere sphere--2" />
        <div className="sphere sphere--3" />
        <div className="sphere sphere--4" />
        <div className="sphere sphere--5" />
        <div className="sphere sphere--6" />
        <div className="sphere sphere--7" />
        <div className="sphere sphere--8" />
        <div className="sphere sphere--9" />
        <div className="sphere sphere--10" />
        <div className="sphere sphere--11" />
        <div className="sphere sphere--12" />
      </div>

      {/* ── Hero Content ── */}
      <div className="home__content">
        {/* Badge */}
        <div className="home__badge">
          <span className="home__badge-dot" />
          AI-Powered Platform
        </div>

        {/* Headline */}
        <h1 className="home__headline">
          <span className="home__headline-blue">Automate</span> your workflow{" "}
          <br />
          with AI Agents
        </h1>

        {/* Subtitle */}
        <p className="home__sub">
          Boost your productivity with{" "}
          <span className="home__sub-accent">AI-powered</span> agents for task
          automation, smart workflows, and intelligent decision-making.
        </p>

        {/* CTA */}
        <a href="signup" className="home__cta">
          Get Started
          <span className="home__cta-arrow">→</span>
        </a>
      </div>
    </section>
  );
};

export default Home;
