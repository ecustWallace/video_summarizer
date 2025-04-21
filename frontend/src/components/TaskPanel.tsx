import { useEffect, useState } from "react";

interface Task {
  id?: number; // ID is crucial now
  keyword: string;
  video_number?: number;
  skip_download?: boolean;
  user_email?: string; // Keep user_email if needed elsewhere, though maybe not for WS connection
}

interface TaskPanelProps {
  task: Task;
  onBack: () => void;
}

// Define structure for WebSocket messages (align with backend)
interface ProgressMessage {
    type: 'progress';
    message: string;
}

interface SummaryMessage {
    type: 'summary';
    data: string;
}

interface ErrorMessage {
    type: 'error';
    message: string;
}

type WebSocketMessage = ProgressMessage | SummaryMessage | ErrorMessage;

export default function TaskPanel({ task, onBack }: TaskPanelProps) {
  const [progressMessages, setProgressMessages] = useState<string[]>([]);
  const [summary, setSummary] = useState<string | null>(null);
  // Start in loading state, assume task processing begins immediately after creation
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null); // Optional: state for specific error msg

  useEffect(() => {
    // Only proceed if we have a task with an ID
    if (!task || typeof task.id === 'undefined') {
        setLoading(false); // No task or ID, nothing to load
        return;
    }

    // Reset state when task changes
    setProgressMessages([]);
    setSummary(null);
    setError(null);
    setLoading(true);

    // Option 1: Pass task ID in URL (if backend supports it)
    const wsUrl = `wss://backend-468274160217.us-central1.run.app/ws/progress/${task.id}`;
    // Option 2: Generic URL (if backend expects subscription message)
    // const wsUrl = "wss://backend-468274160217.us-central1.run.app/ws/progress";

    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      console.log("WebSocket connected for task:", task.id);
      // Option 2 continuation: Send subscription message if needed
      // socket.send(JSON.stringify({ type: 'subscribe', taskId: task.id }));
      setProgressMessages((prev) => [...prev, "▶️ WebSocket connected. Waiting for progress..."]);
    };

    socket.onmessage = (event) => {
      try {
        const receivedData: WebSocketMessage = JSON.parse(event.data);

        // Check the type of message received
        if (receivedData.type === 'progress') {
          setProgressMessages((prev) => [...prev, receivedData.message]);
        } else if (receivedData.type === 'summary') {
          setSummary(receivedData.data);
          setProgressMessages((prev) => [...prev, "✅ Summary received."]);
          setLoading(false); // Task finished successfully
          socket.close(); // Optional: Close socket if task is complete
        } else if (receivedData.type === 'error') {
          setError(receivedData.message); // Store specific error
          setProgressMessages((prev) => [...prev, `❌ Error: ${receivedData.message}`]);
          setLoading(false); // Task finished with error
          socket.close(); // Optional: Close socket if task is complete
        } else {
           // Handle unknown message types if necessary
           console.warn("Received unknown WebSocket message type:", receivedData);
           setProgressMessages((prev) => [...prev, `[Unknown message]: ${event.data}`]);
        }
      } catch (e) {
        console.error("Failed to parse WebSocket message or invalid format:", event.data, e);
        // Display raw message if parsing fails
        setProgressMessages((prev) => [...prev, `[Raw]: ${event.data}`]);
      }
    };

    socket.onerror = (error) => {
      console.error("WebSocket Error:", error);
      setError("WebSocket connection error.");
      setProgressMessages((prev) => [...prev, "❌ WebSocket connection error."]);
      setLoading(false);
    };

    socket.onclose = (event) => {
      console.log("WebSocket closed:", event.reason);
      // If loading is still true here, it means the socket closed before completion
      if (loading && !summary && !error) {
         setProgressMessages((prev) => [...prev, "⏹️ WebSocket closed unexpectedly."]);
         setError("Connection closed before task completion.");
         setLoading(false);
      }
    };

    // Cleanup function: Close the socket when the component unmounts or the task changes
    return () => {
      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
         socket.close();
      }
    };
    // Dependency array: Re-run effect if the task ID changes
  }, [task?.id]); // Depend only on task.id, or task itself if other props matter for WS setup

  // Render logic remains similar, but now relies purely on WebSocket updates
  return (
    <div className="p-4">
      <button onClick={onBack} className="text-blue-500 underline mb-4">
        ← Back to Task List
      </button>

      {task ? (
        <>
          <h2 className="text-xl font-bold mb-2">Task: {task.keyword} (#{task.id})</h2>
          <div className="bg-gray-900 rounded p-4 mb-4 max-h-60 overflow-y-scroll text-sm">
            {progressMessages.map((msg, idx) => (
              <div key={idx}>{msg}</div>
            ))}
            {/* Keep loading indicator while task is running */}
            {loading && <div>⏳ Processing task...</div>}
            {error && !loading && <div className="text-red-500">⚠️ Task failed: {error}</div>}
          </div>

          {summary && !loading && (
            <div className="bg-white text-black p-4 rounded shadow">
              <h3 className="font-semibold mb-2">✅ Final Summary</h3>
              <p>{summary}</p>
            </div>
          )}
        </>
       ) : (
         <div>No task selected or task data is missing.</div>
       )
      }
    </div>
  );
}