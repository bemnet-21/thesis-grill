import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getNextQuestion, submitAnswer } from "../lib/api";
import { Send, Loader2, RefreshCw } from "lucide-react";

export default function SessionView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [question, setQuestion] = useState<any>(null);
  const [transcript, setTranscript] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchNextQuestion();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const fetchNextQuestion = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getNextQuestion(id!);
      if (data.isFinished) {
        navigate(`/report/${id}`);
      } else {
        setQuestion(data);
      }
    } catch (err: any) {
      setError(err.message || "Failed to fetch question");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!transcript.trim()) return;
    
    setIsLoading(true);
    setError(null);
    const answerToSubmit = transcript;
    setTranscript("");

    try {
      await submitAnswer(id!, answerToSubmit);
      await fetchNextQuestion();
    } catch (err: any) {
      setError(err.message || "Failed to submit answer");
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[80vh] max-w-3xl mx-auto p-4">
      <div className="flex-1 bg-[#2a2a2a] rounded-xl shadow-xl overflow-hidden flex flex-col">
        <div className="bg-[#1a1a1a] p-4 border-b border-gray-700 flex justify-between items-center">
          <h2 className="text-lg font-semibold text-white">Defense Session</h2>
          {question && (
            <span className="px-3 py-1 bg-purple-900/50 text-purple-200 rounded-full text-sm font-medium">
              {question.rubric_category}
            </span>
          )}
        </div>

        <div className="flex-1 p-6 flex flex-col justify-center relative">
          {isLoading ? (
            <div className="flex flex-col items-center text-gray-400">
              <Loader2 className="w-10 h-10 animate-spin mb-4" />
              <p>Thinking...</p>
            </div>
          ) : error ? (
            <div className="text-center text-red-400">
              <p>{error}</p>
              <button onClick={fetchNextQuestion} className="mt-4 flex items-center justify-center mx-auto px-4 py-2 bg-[#333] hover:bg-[#444] rounded-lg">
                <RefreshCw className="w-4 h-4 mr-2" /> Retry
              </button>
            </div>
          ) : (
            <div className="text-center">
              <h3 className="text-2xl font-medium text-white mb-8 leading-relaxed">
                "{question?.text}"
              </h3>
            </div>
          )}
        </div>

        <div className="p-4 bg-[#1a1a1a] border-t border-gray-700">
          <form onSubmit={handleSubmit} className="relative">
            <input
              type="text"
              value={transcript}
              onChange={(e) => setTranscript(e.target.value)}
              placeholder="Type your answer here..."
              disabled={isLoading}
              className="w-full bg-[#2a2a2a] border border-gray-600 rounded-lg px-4 py-4 pr-12 text-white focus:outline-none focus:border-purple-500 disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={isLoading || !transcript.trim()}
              className="absolute right-2 top-2 p-2 bg-purple-600 hover:bg-purple-700 text-white rounded-md disabled:opacity-50 transition-colors"
            >
              <Send className="w-5 h-5" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
