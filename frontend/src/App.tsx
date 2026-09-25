import { BrowserRouter, Routes, Route } from "react-router-dom";
import { VoxideClient, VoxideWidget } from "@voxide/react";

import UploadScreen from "./components/UploadScreen";
import SessionView from "./components/SessionView";
import ReportView from "./components/ReportView";

const ai = new VoxideClient({
  publicKey: import.meta.env.VITE_VOXIDE_PUBLIC_KEY || "vox_pub_...",
});

function App() {
  return (
    <BrowserRouter>
      {/* VoxideWidget is at the root so it survives navigation */}
      <VoxideWidget client={ai} />
      
      <main className="min-h-screen bg-[#111] text-gray-100 font-sans">
        <header className="border-b border-gray-800 p-4">
          <div className="max-w-7xl mx-auto flex items-center">
            <h1 className="text-xl font-bold bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">
              MeRmra Exam
            </h1>
          </div>
        </header>

        <Routes>
          <Route path="/" element={<UploadScreen />} />
          <Route path="/session/:id" element={<SessionView />} />
          <Route path="/report/:id" element={<ReportView />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}

export default App;
