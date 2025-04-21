import { useState } from "react";
import { motion } from "framer-motion";
import { GoogleLogin, GoogleOAuthProvider, CredentialResponse } from "@react-oauth/google";
import { useNavigate } from "react-router-dom";
import { useAuth } from "./auth";


export default function Home() {
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const navigate = useNavigate();
  const { setEmail } = useAuth();

  const handleGoogleLogin = (credentialResponse: CredentialResponse) => {
    const token = credentialResponse.credential;

    if (!token) {
      console.error("No token returned");
      return;
    }

    try {
      const decoded = JSON.parse(atob(token.split(".")[1]));
      setUserEmail(decoded.email);
      setEmail(decoded.email);
      navigate("/dashboard");
    } catch (error) {
      console.error("Failed to decode token", error);
    }
  };

  return (
    <GoogleOAuthProvider clientId="468274160217-cou5j4uvk41mvlrlppsd8n3ac4cg4ggp.apps.googleusercontent.com">
      <div className="min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-gray-800 text-white px-6 py-16">
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1 }}
          className="text-center mb-20"
        >
          <h1 className="text-6xl font-extrabold mb-4 bg-gradient-to-r from-purple-400 to-pink-600 text-transparent bg-clip-text">
            Wallace TikTok Topic Summarizer
          </h1>
          <p className="text-xl text-gray-300 max-w-xl mx-auto">
            Explore what's trending on TikTok through AI-powered summarization. Powered by Gemini and Retrieval-Augmented Generation (RAG).
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.3, duration: 0.8 }}
          className="max-w-md mx-auto bg-gray-900 p-8 rounded-2xl shadow-2xl text-center"
        >
          <h2 className="text-2xl font-bold mb-4">Login with Google</h2>
          {userEmail ? (
            <p className="text-green-400">✅ Logged in as: {userEmail}</p>
          ) : (
            <div className="w-fit mx-auto">
              <GoogleLogin
                onSuccess={handleGoogleLogin}
                onError={() => console.log("Login Failed")}
              />
            </div>
          )}
        </motion.div>
      </div>
    </GoogleOAuthProvider>
  );
}
