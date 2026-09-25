import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import SessionView from "../components/SessionView";

// Mock the API module
vi.mock("../lib/api", () => ({
  getNextQuestion: vi.fn(),
  submitAnswer: vi.fn(),
}));

import * as api from "../lib/api";

describe("SessionView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderComponent = () =>
    render(
      <BrowserRouter>
        <Routes>
          <Route path="/session/:id" element={<SessionView />} />
        </Routes>
      </BrowserRouter>
    );

  it("should fetch initial question, handle submit, and fetch next question", async () => {
    // Initial load question
    vi.mocked(api.getNextQuestion).mockResolvedValueOnce({
      id: "q1",
      rubric_category: "Methodology",
      text: "How did you design your experiments?",
      isFinished: false
    });
    
    // Submitting answer resolves successfully
    vi.mocked(api.submitAnswer).mockResolvedValueOnce({ pushback: false });
    
    // Second fetch resolves with next question
    vi.mocked(api.getNextQuestion).mockResolvedValueOnce({
      id: "q2",
      rubric_category: "Results",
      text: "What were your main findings?",
      isFinished: false
    });

    // We need to set the URL correctly for the router
    window.history.pushState({}, "Test page", "/session/123");
    renderComponent();

    // Verify initial load
    expect(screen.getByText("Thinking...")).toBeInTheDocument();
    
    await waitFor(() => {
      expect(screen.getByText(/How did you design your experiments\?/i)).toBeInTheDocument();
      expect(screen.getByText("Methodology")).toBeInTheDocument();
    });

    // Fill in the input
    const input = screen.getByPlaceholderText("Type your answer here...");
    fireEvent.change(input, { target: { value: "I used a randomized controlled trial." } });
    
    // Submit
    const submitBtn = screen.getByRole("button");
    fireEvent.click(submitBtn);

    // Expect loading state while submitting
    expect(screen.getByText("Thinking...")).toBeInTheDocument();
    
    // Check API calls
    await waitFor(() => {
      expect(api.submitAnswer).toHaveBeenCalledWith("123", "I used a randomized controlled trial.");
    });

    // Expect next question to appear
    await waitFor(() => {
      expect(screen.getByText(/What were your main findings\?/i)).toBeInTheDocument();
      expect(screen.getByText("Results")).toBeInTheDocument();
    });
    
    // Input should be cleared
    expect(input).toHaveValue("");
  });
});
