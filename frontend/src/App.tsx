import { useState } from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import { AuthContext } from "./auth";
import Home from "./Home";
import Dashboard from "./Dashboard";

export default function App() {
  const [email, setEmail] = useState<string | null>(null);

  return (
    <AuthContext.Provider value={{ email, setEmail }}>
      <Router>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/dashboard" element={<Dashboard />} />
        </Routes>
      </Router>
    </AuthContext.Provider>
  );
}