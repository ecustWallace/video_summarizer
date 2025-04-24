import { useEffect, useState } from "react";

interface Task {
  id?: number; // ID is crucial now
  keyword: string;
  video_number?: number;
  skip_download?: boolean;
  user_email?: string; // Keep user_email if needed elsewhere, though maybe not for WS connection
  status?: string;
  summary?: string | null;
  created_at?: string | null;
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
  const [summary, setSummary] = useState<string | null>(task.summary || null);
  const [status, setStatus] = useState<string>(task.status || 'In Progress');
  const [loading, setLoading] = useState(task.status === 'In Progress');
  const [error, setError] = useState<string | null>(null); // Optional: state for specific error msg

  useEffect(() => {
    // Only proceed if we have a task with an ID
    if (!task || typeof task.id === 'undefined') {
        setLoading(false);
        return;
    }

    // Reset state when task changes
    setProgressMessages([]);
    setSummary(task.summary || null);
    setStatus(task.status || 'In Progress');
    setError(null);
    setLoading(task.status === 'In Progress');

    // Only connect to WebSocket if task is in progress
    if (task.status === 'In Progress') {
        const wsUrl = `wss://backend-468274160217.us-central1.run.app/ws/progress/${task.id}`;
        const socket = new WebSocket(wsUrl);

        socket.onopen = () => {
            console.log("WebSocket connected for task:", task.id);
            setProgressMessages((prev) => [...prev, "▶️ WebSocket connected. Waiting for progress..."]);
        };

        socket.onmessage = (event) => {
            try {
                const receivedData: WebSocketMessage = JSON.parse(event.data);

                if (receivedData.type === 'progress') {
                    setProgressMessages((prev) => [...prev, receivedData.message]);
                } else if (receivedData.type === 'summary') {
                    setSummary(receivedData.data);
                    setStatus('Done');
                    setProgressMessages((prev) => [...prev, "✅ Summary received."]);
                    setLoading(false);
                    socket.close();
                } else if (receivedData.type === 'error') {
                    setError(receivedData.message);
                    setStatus('Failed');
                    setProgressMessages((prev) => [...prev, `❌ Error: ${receivedData.message}`]);
                    setLoading(false);
                    socket.close();
                } else {
                    console.warn("Received unknown WebSocket message type:", receivedData);
                    setProgressMessages((prev) => [...prev, `[Unknown message]: ${event.data}`]);
                }
            } catch (e) {
                console.error("Failed to parse WebSocket message:", event.data, e);
                setProgressMessages((prev) => [...prev, `[Raw]: ${event.data}`]);
            }
        };

        socket.onerror = (error) => {
            console.error("WebSocket Error:", error);
            setError("WebSocket connection error.");
            setStatus('Failed');
            setProgressMessages((prev) => [...prev, "❌ WebSocket connection error."]);
            setLoading(false);
        };

        socket.onclose = (event) => {
            console.log("WebSocket closed:", event.reason);
            if (loading && !summary && !error) {
                setProgressMessages((prev) => [...prev, "⏹️ WebSocket closed unexpectedly."]);
                setError("Connection closed before task completion.");
                setStatus('Failed');
                setLoading(false);
            }
        };

        return () => {
            if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
                socket.close();
            }
        };
    }
  }, [task?.id, task?.status, task?.summary]);

  return (
    <div className="p-4">
      <button onClick={onBack} className="text-blue-500 underline mb-4">
        ← Back to Task List
      </button>

      {task ? (
        <>
          <h2 className="text-xl font-bold mb-2">Task: {task.keyword} (#{task.id})</h2>
          <div className="mb-4">
            <span className={`inline-block px-3 py-1 rounded-full text-sm ${
              status === 'Done' ? 'bg-green-500' :
              status === 'Failed' ? 'bg-red-500' :
              'bg-yellow-500'
            }`}>
              {status}
            </span>
            {task.created_at && (
              <span className="ml-4 text-gray-400">
                Created: {new Date(task.created_at).toLocaleString()}
              </span>
            )}
          </div>
          
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