import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "./auth";
import TaskPanel from "@/components/TaskPanel";
import { apiUrl, wsUrl } from "./config";

interface Task {
  id?: number;
  keyword: string;
  number?: number;
  skip_download?: boolean;
  user_email?: string;
  status?: string;
  summary?: string | null;
  created_at?: string | null;
}

interface WebSocketMessage {
  type: 'progress' | 'summary' | 'error';
  message?: string;
  data?: string;
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
  const [isPolling, setIsPolling] = useState(true);
  const [socket, setSocket] = useState<WebSocket | null>(null);
  const [progressMessages, setProgressMessages] = useState<string[]>([]);

  const fetchTasks = async () => {
    if (!email || !isPolling) return;
    try {
      const response = await fetch(`${apiUrl}/api/tasks?email=${email}`);
      const data = await response.json();
      setTasks(data.tasks);
      
      if (selectedTask) {
        const updatedTask = data.tasks.find((t: Task) => t.id === selectedTask.id);
        if (updatedTask) {
          setSelectedTask(updatedTask);
          if (updatedTask.status === 'Done' || updatedTask.status === 'Failed') {
            setIsPolling(false);
            if (socket) {
              socket.close();
              setSocket(null);
            }
          }
        }
      }
    } catch (err) {
      console.error("Failed to load tasks", err);
    }
  };

  // WebSocket 连接管理
  useEffect(() => {
    if (!selectedTask || selectedTask.status !== 'In Progress') {
      if (socket) {
        socket.close();
        setSocket(null);
      }
      return;
    }

    const wsUrlWithTask = `${wsUrl}/ws/progress/${selectedTask.id}`;
    const newSocket = new WebSocket(wsUrlWithTask);
    setSocket(newSocket);

    newSocket.onopen = () => {
      setProgressMessages(["▶️ WebSocket connected. Waiting for progress..."]);
      console.log("WebSocket connected for task:", selectedTask.id);
    };

    newSocket.onmessage = (event) => {
      try {
        const data: WebSocketMessage = JSON.parse(event.data);
        if (data.type === 'progress' && data.message) {
          setProgressMessages(prev => [...prev, data.message!]);
        } else if (data.type === 'summary' && data.data) {
          setSelectedTask(prev => prev ? { ...prev, status: 'Done', summary: data.data! } : null);
          setProgressMessages(prev => [...prev, "✅ Summary received."]);
          newSocket.close();
          setSocket(null);
        } else if (data.type === 'error' && data.message) {
          setSelectedTask(prev => prev ? { ...prev, status: 'Failed' } : null);
          setProgressMessages(prev => [...prev, `❌ Error: ${data.message}`]);
          newSocket.close();
          setSocket(null);
        }
      } catch (e) {
        console.error("Failed to parse WebSocket message:", e);
      }
    };

    newSocket.onerror = (error) => {
      console.error("WebSocket Error:", error);
      setProgressMessages(prev => [...prev, "❌ WebSocket connection error."]);
    };

    newSocket.onclose = () => {
      console.log("WebSocket closed");
      setSocket(null);
    };

    return () => {
      if (newSocket.readyState === WebSocket.OPEN || newSocket.readyState === WebSocket.CONNECTING) {
        newSocket.close();
      }
    };
  }, [selectedTask?.id, selectedTask?.status]);

  useEffect(() => {
    if (!email) {
      navigate("/");
    } else {
      fetch(`${apiUrl}/api/users/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });

      fetchTasks();

      const interval = setInterval(fetchTasks, 2000);

      return () => {
        clearInterval(interval);
        setIsPolling(true);
      };
    }
  }, [email, navigate]);

  if (!email) return null;

  const handleLogout = () => {
    setEmail(null);
    navigate("/");
  };

  const handleSubmit = () => {
    const taskPayload = skipDownload ? { keyword, number, email, skip_download: true } : { keyword, number, email, skip_download: false };
    fetch(`${apiUrl}/api/tasks/create`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(taskPayload),
    })
      .then((res) => {
        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`);
        }
        return res.json();
      })
      .then((data) => {
        const newTask = data.task;
        // 1. 先更新任务列表
        setTasks((prevTasks) => [...prevTasks, newTask]);
        
        // 2. 重置表单状态
        setShowModal(false);
        setKeyword("");
        setNumber(10);
        setSkipDownload(false);
        
        // 3. 重置进度消息
        setProgressMessages([]);
        
        // 4. 设置选中的任务
        setSelectedTask({ ...newTask, user_email: email });
        
        // 5. 启用轮询
        setIsPolling(true);
        
        // 6. 立即建立 WebSocket 连接
        if (newTask.id) {
          const wsUrlWithTask = `${wsUrl}/ws/progress/${newTask.id}`;
          const newSocket = new WebSocket(wsUrlWithTask);
          setSocket(newSocket);
          
          newSocket.onopen = () => {
            console.log("WebSocket connected for task:", newTask.id);
            setProgressMessages(["▶️ WebSocket connected. Waiting for progress..."]);
          };
          
          newSocket.onmessage = (event) => {
            try {
              const data: WebSocketMessage = JSON.parse(event.data);
              if (data.type === 'progress' && data.message) {
                setProgressMessages(prev => [...prev, data.message!]);
              } else if (data.type === 'summary' && data.data) {
                setSelectedTask(prev => prev ? { ...prev, status: 'Done', summary: data.data! } : null);
                setProgressMessages(prev => [...prev, "✅ Summary received."]);
                newSocket.close();
                setSocket(null);
              } else if (data.type === 'error' && data.message) {
                setSelectedTask(prev => prev ? { ...prev, status: 'Failed' } : null);
                setProgressMessages(prev => [...prev, `❌ Error: ${data.message}`]);
                newSocket.close();
                setSocket(null);
              }
            } catch (e) {
              console.error("Failed to parse WebSocket message:", e);
            }
          };
          
          newSocket.onerror = (error) => {
            console.error("WebSocket Error:", error);
            setProgressMessages(prev => [...prev, "❌ WebSocket connection error."]);
          };
          
          newSocket.onclose = () => {
            console.log("WebSocket closed");
            setSocket(null);
          };
        }
      })
      .catch((err) => {
        console.error("Failed to create or start task", err);
      });
  };

  const handleDelete = (taskId: number) => {
    fetch(`${apiUrl}/api/tasks/delete/${taskId}`, {
      method: "DELETE",
    })
      .then((res) => {
        if (!res.ok) throw new Error("Delete failed");
        setTasks(tasks.filter((task) => task.id !== taskId));
        if (selectedTask?.id === taskId) {
          setSelectedTask(null);
          setProgressMessages([]);
          setIsPolling(false);
        }
      })
      .catch((err) => console.error("Failed to delete task", err));
  };

  const handleBack = () => {
    setSelectedTask(null);
    setProgressMessages([]);
    setIsPolling(false);
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
                  onClick={() => {
                    setSelectedTask(task);
                    setProgressMessages([]);
                    setIsPolling(true);
                  }}
                  className="cursor-pointer hover:text-blue-400"
                >
                  {task.keyword}
                  {task.status && (
                    <span className={`ml-2 text-xs px-2 py-1 rounded-full ${
                      task.status === 'Done' ? 'bg-green-500' :
                      task.status === 'Failed' ? 'bg-red-500' :
                      'bg-yellow-500'
                    }`}>
                      {task.status}
                    </span>
                  )}
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
            onClick={handleBack}
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
          <TaskPanel 
            task={selectedTask} 
            onBack={handleBack}
            progressMessages={progressMessages}
            setProgressMessages={setProgressMessages}
          />
        ) : (
          <div className="text-center">
            <h1 className="text-5xl font-bold text-gray-100">
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

            <div className="flex justify-end space-x-2">
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