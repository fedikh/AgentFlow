import React, { useState } from "react";
import LoginPage from "./LoginPage";
import SignUpPage from "./SignUpPage";
import ForgotPasswordPage from "./ForgotPasswordPage";

const AuthRouter = () => {
  const [page, setPage] = useState("login");

  return (
    <div className="auth-root">
      {page === "login" && <LoginPage onNavigate={setPage} />}
      {page === "signup" && <SignUpPage onNavigate={setPage} />}
      {page === "forgot" && <ForgotPasswordPage onNavigate={setPage} />}
    </div>
  );
};

export default AuthRouter;
