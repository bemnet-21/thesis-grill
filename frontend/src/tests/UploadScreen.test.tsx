import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { BrowserRouter } from "react-router-dom";
import UploadScreen from "../components/UploadScreen";

// Mock the API module
vi.mock("../lib/api", () => ({
  uploadThesis: vi.fn(),
  checkThesisStatus: vi.fn(),
  startSession: vi.fn(),
}));

import * as api from "../lib/api";

describe("UploadScreen", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderComponent = () =>
    render(
      <BrowserRouter>
        <UploadScreen />
      </BrowserRouter>
    );

  it("should upload a file and transition to status polling", async () => {
    const mockUpload = vi.mocked(api.uploadThesis).mockResolvedValue({ id: "123", ingestion_status: "pending" });
    const mockCheckStatus = vi.mocked(api.checkThesisStatus).mockResolvedValue({ ingestion_status: "ready" });
    
    renderComponent();

    // Fill out the form
    fireEvent.change(screen.getByPlaceholderText("Enter thesis title..."), { target: { value: "Test Thesis" } });
    
    const file = new File(["dummy content"], "test.pdf", { type: "application/pdf" });
    const fileInput = screen.getByLabelText(/Click to upload/i) as HTMLInputElement;
    // We target the input itself inside the label, not the text directly
    const actualInput = fileInput.parentElement?.querySelector("input") || document.querySelector("input[type='file']");
    fireEvent.change(actualInput!, { target: { files: [file] } });

    // Submit form
    const form = screen.getByRole('button', { name: /upload/i }).closest('form');
    fireEvent.submit(form!);

    await waitFor(() => {
      expect(mockUpload).toHaveBeenCalledWith(file, "Test Thesis");
    });

    // Check polling behavior - should show status loading, then update when polling happens
    expect(screen.getByText("pending")).toBeInTheDocument();
    
    // Simulate interval fetching
    await waitFor(() => {
       expect(mockCheckStatus).toHaveBeenCalledWith("123");
    }, { timeout: 2500 });
    
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Start Defense/i })).toBeInTheDocument();
    });
  });
});
