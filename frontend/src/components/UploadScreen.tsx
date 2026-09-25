import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { uploadThesis, checkThesisStatus, startSession } from "../lib/api";
import { Upload, FileText, Loader2, Play } from "lucide-react";

export default function UploadScreen() {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [thesisId, setThesisId] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;
    if (thesisId && status && status !== "ready" && status !== "failed") {
      interval = setInterval(async () => {
        try {
          const data = await checkThesisStatus(thesisId);
          setStatus(data.ingestion_status);
        } catch (err) {
          console.error("Status check failed", err);
        }
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [thesisId, status]);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !title) return;
    setIsUploading(true);
    setError(null);
    try {
      const data = await uploadThesis(file, title);
      setThesisId(data.id);
      setStatus(data.ingestion_status);
    } catch (err: any) {
      setError(err.message || "Failed to upload thesis");
    } finally {
      setIsUploading(false);
    }
  };

  const handleStartSession = async () => {
    if (!thesisId) return;
    setIsStarting(true);
    try {
      const data = await startSession(thesisId, "en");
      navigate(`/session/${data.id}`);
    } catch (err: any) {
      setError(err.message || "Failed to start session");
      setIsStarting(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-[80vh] p-4">
      <div className="max-w-md w-full bg-[#2a2a2a] p-8 rounded-xl shadow-xl">
        <h1 className="text-3xl font-bold mb-6 text-center text-white">Upload Thesis</h1>

        {!thesisId ? (
          <form onSubmit={handleUpload} className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Thesis Title</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full bg-[#1a1a1a] border border-gray-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-purple-500"
                placeholder="Enter thesis title..."
                required
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">PDF Document</label>
              <div className="flex items-center justify-center w-full">
                <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed border-gray-600 rounded-lg cursor-pointer bg-[#1a1a1a] hover:bg-[#222]">
                  <div className="flex flex-col items-center justify-center pt-5 pb-6">
                    <Upload className="w-8 h-8 mb-2 text-gray-400" />
                    <p className="mb-2 text-sm text-gray-400">
                      <span className="font-semibold">Click to upload</span> or drag and drop
                    </p>
                    {file && <p className="text-sm text-purple-400">{file.name}</p>}
                  </div>
                  <input
                    type="file"
                    className="hidden"
                    accept=".pdf"
                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                    required
                  />
                </label>
              </div>
            </div>

            {error && <p className="text-red-400 text-sm text-center">{error}</p>}

            <button
              type="submit"
              disabled={isUploading || !file || !title}
              className="w-full flex justify-center items-center py-3 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-purple-600 hover:bg-purple-700 focus:outline-none disabled:opacity-50"
            >
              {isUploading ? <Loader2 className="w-5 h-5 animate-spin" /> : "Upload"}
            </button>
          </form>
        ) : (
          <div className="flex flex-col items-center space-y-6 text-center">
            <div className="bg-[#1a1a1a] p-6 rounded-full">
              <FileText className="w-12 h-12 text-purple-400" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-white mb-2">{title}</h2>
              <div className="flex items-center justify-center space-x-2 text-gray-300">
                {status !== "ready" && status !== "failed" && <Loader2 className="w-4 h-4 animate-spin" />}
                <span className="capitalize">{status}</span>
              </div>
            </div>

            {error && <p className="text-red-400 text-sm">{error}</p>}

            {status === "failed" && (
              <p className="text-red-400">Ingestion failed. Please try a different PDF.</p>
            )}

            {status === "ready" && (
              <button
                onClick={handleStartSession}
                disabled={isStarting}
                className="w-full flex justify-center items-center py-3 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-green-600 hover:bg-green-700 focus:outline-none disabled:opacity-50 mt-4"
              >
                {isStarting ? <Loader2 className="w-5 h-5 animate-spin mr-2" /> : <Play className="w-5 h-5 mr-2" />}
                Start Defense
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
