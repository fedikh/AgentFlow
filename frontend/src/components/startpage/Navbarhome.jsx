import { useState, useEffect } from "react";
import { Menu, X, LogIn, UserPlus } from "lucide-react";
import "../../styles/startpage/navbarhome.css";

const Navbarhome = () => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [activeLink, setActiveLink] = useState("Home");

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 40);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  useEffect(() => {
    const sectionIds = ["home", "about", "services", "faq"];
    const observers = [];

    sectionIds.forEach((id) => {
      const el = document.getElementById(id);
      if (!el) return;

      const observer = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) {
            setActiveLink(id.charAt(0).toUpperCase() + id.slice(1));
          }
        },
        { threshold: 0.4 },
      );

      observer.observe(el);
      observers.push(observer);
    });

    return () => observers.forEach((obs) => obs.disconnect());
  }, []);

  const navLinks = [
    { name: "Home", href: "#home" },
    { name: "About", href: "#about" },
    { name: "Services", href: "#services" },
    { name: "FAQ", href: "#faq" },
  ];

  return (
    <nav className={`navbar ${scrolled ? "navbar--scrolled" : "navbar--top"}`}>
      <div className="navbar__inner">
        {/* Logo */}
        <a href="#home" className="navbar__logo">
          <img
            src="/src/assets/Logo/Agentflowlogowithouttext.png"
            alt="AgentFlow"
            className="navbar__logo-img"
            onError={(e) => {
              e.target.style.display = "none";
            }}
          />
          <div className="navbar__logo-text">
            <span className="navbar__logo-name">
              AgentFlow<span className="navbar__logo-ai">.AI</span>
            </span>
            <span className="navbar__logo-slogan">Studio of Agents · v1.0</span>
          </div>
        </a>

        {/* Center Pill Nav */}
        <div className="navbar__pill">
          {navLinks.map((link) => (
            <a
              key={link.name}
              href={link.href}
              className={`navbar__link ${activeLink === link.name ? "active" : ""}`}
              onClick={() => setActiveLink(link.name)}
            >
              {link.name}
            </a>
          ))}
        </div>

        {/* Auth Buttons */}
        <div className="navbar__auth">
          <a href="login" className="navbar__btn navbar__btn--ghost">
            Login
          </a>
          <a href="signup" className="navbar__btn navbar__btn--solid">
            Sign Up
          </a>
        </div>

        {/* Mobile Hamburger */}
        <button
          className="navbar__hamburger"
          onClick={() => setIsMenuOpen(!isMenuOpen)}
          aria-label="Toggle menu"
        >
          {isMenuOpen ? <X size={18} /> : <Menu size={18} />}
        </button>
      </div>

      {/* Mobile Dropdown */}
      <div
        className={`navbar__mobile ${isMenuOpen ? "navbar__mobile--open" : ""}`}
      >
        <div className="navbar__mobile-inner">
          {navLinks.map((link) => (
            <a
              key={link.name}
              href={link.href}
              className="navbar__mobile-link"
              onClick={() => setIsMenuOpen(false)}
            >
              {link.name}
            </a>
          ))}
          <div className="navbar__mobile-divider" />
          <div className="navbar__mobile-auth">
            <a
              href="login"
              className="navbar__btn navbar__btn--ghost"
              style={{ justifyContent: "center" }}
            >
              Login
            </a>
            <a
              href="\signup"
              className="navbar__btn navbar__btn--solid"
              style={{ justifyContent: "center" }}
            >
              Sign Up
            </a>
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navbarhome;
