import React, { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { getReport } from "../lib/api";
import { Loader2, Award, ArrowLeft } from "lucide-react";

export default function ReportView() {
  const { id } = useParams<{ id: string }>();
  const [report, setReport] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchReport();
  }, [id]);

  const fetchReport = async () => {
    setIsLoading(true);
    try {
      const data = await getReport(id!);
      setReport(data);
    } catch (err: any) {
      setError(err.message || "Failed to fetch report");
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[80vh] text-gray-400">
        <Loader2 className="w-12 h-12 animate-spin mb-4" />
        <p>Generating your defense report...</p>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="text-center text-red-400 mt-20">
        <p>{error || "Report not found"}</p>
        <Link to="/" className="inline-block mt-4 text-purple-400 hover:underline">
          Return Home
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-4 py-8">
      <div className="bg-[#2a2a2a] rounded-2xl shadow-2xl overflow-hidden">
        <div className="bg-purple-900/40 p-8 text-center border-b border-gray-700">
          <Award className="w-16 h-16 mx-auto mb-4 text-purple-400" />
          <h1 className="text-3xl font-bold text-white mb-2">Defense Report</h1>
          <div className="inline-flex items-baseline justify-center">
            <span className="text-6xl font-extrabold text-white">{report.overall_score}</span>
            <span className="text-2xl text-gray-400 ml-1">/10</span>
          </div>
        </div>

        <div className="p-8 grid md:grid-cols-2 gap-8">
          <div>
            <h2 className="text-xl font-semibold text-white mb-4">Strengths</h2>
            <div className="bg-[#1a1a1a] p-4 rounded-lg text-gray-300">
              {report.strengths || "No strengths recorded."}
            </div>
            
            <h2 className="text-xl font-semibold text-white mt-6 mb-4">Areas for Improvement</h2>
            <div className="bg-[#1a1a1a] p-4 rounded-lg text-gray-300">
              {report.weaknesses || "No weaknesses recorded."}
            </div>
          </div>

          <div>
            <h2 className="text-xl font-semibold text-white mb-4">Category Breakdown</h2>
            <div className="space-y-4">
              {report.per_category_breakdown && Object.entries(report.per_category_breakdown).map(([cat, score]) => (
                <div key={cat} className="bg-[#1a1a1a] p-4 rounded-lg flex justify-between items-center">
                  <span className="text-gray-300 font-medium">{cat}</span>
                  <div className="flex items-center">
                    <div className="w-32 h-2 bg-gray-700 rounded-full mr-3 overflow-hidden">
                      <div 
                        className="h-full bg-purple-500 rounded-full" 
                        style={{ width: `${(Number(score) / 10) * 100}%` }}
                      ></div>
                    </div>
                    <span className="text-white font-semibold">{String(score)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
        
        <div className="p-6 bg-[#1a1a1a] border-t border-gray-700 text-center">
          <Link to="/" className="inline-flex items-center text-purple-400 hover:text-purple-300 font-medium transition-colors">
            <ArrowLeft className="w-5 h-5 mr-2" />
            Start New Session
          </Link>
        </div>
      </div>
    </div>
  );
}
