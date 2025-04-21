import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "./auth";
import TaskPanel from "@/components/TaskPanel";

interface Task {
  id?: number;
  keyword: string;
  number?: number;
  skip_download?: boolean;
  user_email?: string;
}

export default function Dashboard() {
  const { email, setEmail } = useAuth();
  const navigate = useNavigate();
  const [showModal, setShowModal] = useState(false);
  const [keyword, setKeyword] = useState("");
  const [number, setNumber] = useState(10);
  const [skipDownload, setSkipDownload] = useState(false);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);

  useEffect(() => {
    if (!email) {
      navigate("/");
    } else {
      fetch("https://backend-468274160217.us-central1.run.app/api/users/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });

      fetch(`https://backend-468274160217.us-central1.run.app/api/tasks?email=${email}`)
        .then((res) => res.json())
        .then((data) => setTasks(data.tasks))
        .catch((err) => console.error("Failed to load tasks", err));
    }
  }, [email, navigate]);

  if (!email) return null;

  const handleLogout = () => {
    setEmail(null);
    navigate("/");
  };

  const handleSubmit = () => {
    const taskPayload = skipDownload ? { keyword, number, email, skip_download: true } : { keyword, number, email, skip_download: false };
    // Assume this endpoint now creates the record AND starts the background job
    fetch("https://backend-468274160217.us-central1.run.app/api/tasks/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(taskPayload),
    })
      .then((res) => {
        if (!res.ok) {
           // Handle creation failure properly (e.g., show error message)
           throw new Error(`HTTP error! status: ${res.status}`);
        }
        return res.json();
      })
      .then((data) => {
        const newTask = data.task; // Ensure backend returns the full task object with ID
        setTasks((prevTasks) => [...prevTasks, newTask]); // Use functional update for safety
        setShowModal(false);
        setKeyword("");
        setNumber(10);
        setSkipDownload(false);
        // Select the new task to show the TaskPanel, which will then connect WebSocket
        setSelectedTask({ ...newTask, user_email: email }); // Add email if not returned
      })
      .catch((err) => {
          console.error("Failed to create or start task", err);
          // Optionally show an error message to the user in the UI
      });
  };

  const handleDelete = (taskId: number) => {
    fetch(`https://backend-468274160217.us-central1.run.app/api/tasks/delete/${taskId}`, {
      method: "DELETE",
    })
      .then((res) => {
        if (!res.ok) throw new Error("Delete failed");
        setTasks(tasks.filter((task) => task.id !== taskId));
        if (selectedTask?.id === taskId) setSelectedTask(null);
      })
      .catch((err) => console.error("Failed to delete task", err));
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white flex">
      <div className="w-64 bg-gray-800 p-6 flex flex-col justify-between">
        <div>
          <button
            onClick={() => setShowModal(true)}
            className="bg-blue-500 hover:bg-blue-600 w-full text-white font-semibold py-2 px-4 rounded mb-4"
          >
            + Create Task
          </button>

          <h3 className="text-lg font-semibold mb-2">Your Tasks</h3>
          <ul>
            {tasks.map((task) => (
              <li key={task.id} className="flex justify-between items-center mb-1">
                <span
                  onClick={() => setSelectedTask(task)}
                  className="cursor-pointer hover:text-blue-400"
                >
                  {task.keyword}
                </span>
                <button
                  onClick={() => handleDelete(task.id!)}
                  className="ml-2 text-sm text-red-400 hover:text-red-600"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <button
            onClick={() => setSelectedTask(null)}
            className="bg-gray-600 hover:bg-gray-700 text-white font-semibold py-2 px-4 rounded w-full mb-2"
          >
            ⬅️ Back to Dashboard
          </button>
          <button
            onClick={handleLogout}
            className="bg-red-500 hover:bg-red-600 text-white font-semibold py-2 px-4 rounded w-full"
          >
            Log Out
          </button>
        </div>
      </div>

      <div className="flex-1 p-8">
        {selectedTask && selectedTask.keyword ? (
          <TaskPanel task={selectedTask} onBack={() => setSelectedTask(null)} />
        ) : (
          <div className="text-center">
            <h1 className="text-5xl font-extrabold bg-gradient-to-r text-transparent bg-clip-text">
              Hello, {email?.split("@")[0]} 👋
            </h1>
            <p className="text-xl text-gray-300 leading-loose">Welcome to your personalized dashboard. Ready to create something awesome?</p>
          </div>
        )}
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-gray-800 p-6 rounded-xl shadow-lg w-96">
            <h2 className="text-2xl font-bold mb-4">Create Task</h2>

            <label className="block mb-2 font-medium">Keyword</label>
            <input
              type="text"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              className="w-full px-4 py-2 mb-4 rounded bg-gray-700 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />

            <label className="inline-flex items-center mb-4">
              <input
                type="checkbox"
                checked={skipDownload}
                onChange={(e) => setSkipDownload(e.target.checked)}
                className="mr-2"
              />
              Skip Downloading
            </label>

            {!skipDownload && (
              <>
                <label className="block mb-2 font-medium">Number</label>
                <input
                  type="number"
                  value={number}
                  onChange={(e) => setNumber(Number(e.target.value))}
                  className="w-full px-4 py-2 mb-4 rounded bg-gray-700 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </>
            )}

            <div className="flex justify-end space-x-4">
              <button
                onClick={() => setShowModal(false)}
                className="bg-gray-600 hover:bg-gray-700 text-white py-2 px-4 rounded"
              >
                Close
              </button>
              <button
                onClick={handleSubmit}
                className="bg-blue-500 hover:bg-blue-600 text-white py-2 px-4 rounded"
              >
                Submit
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}