import { useEffect, useState, useRef } from "react";
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
  type: 'progress' | 'summary' | 'error' | 'ping';
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
  const [pubsubEnabled, setPubsubEnabled] = useState<boolean | null>(null);
  
  // 使用useRef来存储重试计数，避免闭包问题
  const retryCountRef = useRef(0);
  const maxRetries = 5;
  const retryDelay = 2000;
  const connectingRef = useRef(false); // 跟踪连接是否正在进行中

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

  // 检查PubSub状态
  const checkPubSubStatus = async () => {
    try {
      const response = await fetch(`${apiUrl}/api/system/pubsub-status`);
      const data = await response.json();
      setPubsubEnabled(data.enabled);
      console.log("PubSub状态:", data.enabled ? "启用" : "禁用");
    } catch (err) {
      console.error("无法获取PubSub状态", err);
      setPubsubEnabled(false);
    }
  };

  // WebSocket 连接管理
  useEffect(() => {
    let heartbeatInterval: NodeJS.Timeout | null = null;
    let connectionTimeout: NodeJS.Timeout | null = null;

    const connectWebSocket = () => {
      // 防止重复连接尝试
      if (connectingRef.current) {
        console.log("Connection attempt already in progress, skipping");
        return;
      }
      
      // 重置连接状态
      connectingRef.current = true;
      
      // 如果没有选中的任务，关闭现有连接
      if (!selectedTask) {
        console.log("No task selected, not connecting WebSocket");
        cleanupWebSocket();
        connectingRef.current = false;
        return;
      }

      // 如果任务不在进行中，关闭现有连接
      if (selectedTask.status !== 'In Progress') {
        console.log(`Task status is ${selectedTask.status}, not connecting WebSocket`);
        cleanupWebSocket();
        connectingRef.current = false;
        return;
      }

      // 清理任何现有的WebSocket连接
      cleanupWebSocket();

      console.log("Setting up WebSocket connection for task:", selectedTask.id);
      const wsUrlWithTask = `${wsUrl}/ws/progress/${selectedTask.id}`;
      console.log("WebSocket URL:", wsUrlWithTask);
      
      // 创建新的WebSocket连接
      const newSocket = new WebSocket(wsUrlWithTask);
      
      // 设置一个超时，如果连接在一定时间内没有打开，则重试
      connectionTimeout = setTimeout(() => {
        if (newSocket.readyState !== WebSocket.OPEN) {
          console.log("WebSocket connection timed out, retrying...");
          newSocket.close();
          
          if (retryCountRef.current < maxRetries) {
            retryCountRef.current++;
            setProgressMessages(prev => [...prev, `🔄 WebSocket连接超时，正在尝试重新连接 (${retryCountRef.current}/${maxRetries})...`]);
            
            // 重置连接状态并延迟重试
            connectingRef.current = false;
            setTimeout(connectWebSocket, retryDelay * retryCountRef.current);
          } else {
            console.error("Max retry attempts reached. Could not connect WebSocket.");
            setProgressMessages(prev => [...prev, "❌ 已达到最大重试次数，停止重连。请刷新页面重试。"]);
            
            // 启用轮询作为备选方案
            setIsPolling(true);
            connectingRef.current = false;
          }
        }
      }, 10000);

      newSocket.onopen = () => {
        console.log("WebSocket connected for task:", selectedTask.id);
        if (connectionTimeout) {
          clearTimeout(connectionTimeout);
          connectionTimeout = null;
        }
        
        // 仅在任务仍在进行中时设置新的socket
        if (selectedTask.status === 'In Progress') {
          setSocket(newSocket);
          setProgressMessages(prev => [...prev, "▶️ WebSocket连接已建立，正在等待进度更新..."]);
          retryCountRef.current = 0; // 重置重试计数
          
          // 设置心跳检测，每30秒发送一次ping
          heartbeatInterval = setInterval(() => {
            if (newSocket.readyState === WebSocket.OPEN) {
              try {
                newSocket.send(JSON.stringify({ type: 'ping' }));
                console.log("Sent ping to keep connection alive");
              } catch (e) {
                console.error("Error sending ping:", e);
                cleanupWebSocket();
                
                // 延迟重连
                connectingRef.current = false;
                setTimeout(connectWebSocket, retryDelay);
              }
            }
          }, 30000);
        } else {
          // 如果任务已不在进行中，立即关闭这个新建立的连接
          console.log("Task no longer in progress, closing new connection");
          newSocket.close();
        }
        
        connectingRef.current = false;
      };

      newSocket.onmessage = (event) => {
        console.log("Received WebSocket message:", event.data);
        try {
          const data: WebSocketMessage = JSON.parse(event.data);
          console.log("Parsed WebSocket message:", data);
          
          if (data.type === 'progress' && data.message) {
            console.log("Processing progress message:", data.message);
            setProgressMessages(prev => [...prev, data.message!]);
          } else if (data.type === 'summary' && data.data) {
            console.log("Processing summary message:", data.data);
            setSelectedTask(prev => prev ? { ...prev, status: 'Done', summary: data.data! } : null);
            setProgressMessages(prev => [...prev, "✅ 摘要已接收。"]);
            // 任务完成时关闭连接
            if (newSocket.readyState === WebSocket.OPEN) {
              newSocket.close();
            }
            setSocket(null);
            if (heartbeatInterval) {
              clearInterval(heartbeatInterval);
              heartbeatInterval = null;
            }
            if (connectionTimeout) {
              clearTimeout(connectionTimeout);
              connectionTimeout = null;
            }
          } else if (data.type === 'error' && data.message) {
            console.log("Processing error message:", data.message);
            setSelectedTask(prev => prev ? { ...prev, status: 'Failed' } : null);
            setProgressMessages(prev => [...prev, `❌ 错误: ${data.message}`]);
            // 任务失败时关闭连接
            if (newSocket.readyState === WebSocket.OPEN) {
              newSocket.close();
            }
            setSocket(null);
            if (heartbeatInterval) {
              clearInterval(heartbeatInterval);
              heartbeatInterval = null;
            }
            if (connectionTimeout) {
              clearTimeout(connectionTimeout);
              connectionTimeout = null;
            }
          } else if (data.type === 'ping') {
            console.log("Received ping from server");
          } else {
            console.warn("Unknown message type:", data);
          }
        } catch (e) {
          console.error("Failed to parse WebSocket message:", event.data, e);
        }
      };

      newSocket.onerror = (error) => {
        console.error("WebSocket Error:", error);
        if (connectionTimeout) {
          clearTimeout(connectionTimeout);
          connectionTimeout = null;
        }
        
        setProgressMessages(prev => [...prev, "❌ WebSocket连接错误，正在尝试重新连接..."]);
        cleanupWebSocket();
        
        // 自动尝试重新连接
        if (retryCountRef.current < maxRetries) {
          retryCountRef.current++;
          
          // 重置连接状态并延迟重试
          connectingRef.current = false;
          setTimeout(connectWebSocket, retryDelay * retryCountRef.current);
        } else {
          setProgressMessages(prev => [...prev, "❌ 已达到最大重试次数，停止重连。切换到轮询模式。"]);
          
          // 切换到轮询模式
          setIsPolling(true);
          connectingRef.current = false;
        }
      };

      newSocket.onclose = (event) => {
        console.log("WebSocket closed with code:", event.code, "reason:", event.reason);
        if (connectionTimeout) {
          clearTimeout(connectionTimeout);
          connectionTimeout = null;
        }
        
        setSocket(null);
        if (heartbeatInterval) {
          clearInterval(heartbeatInterval);
          heartbeatInterval = null;
        }
        
        // 如果任务仍在进行中且未达到最大重试次数，尝试重新连接
        if (selectedTask && selectedTask.status === 'In Progress' && retryCountRef.current < maxRetries) {
          console.log(`Attempting to reconnect (${retryCountRef.current + 1}/${maxRetries})...`);
          setProgressMessages(prev => [...prev, `🔄 WebSocket连接已关闭，正在尝试重新连接 (${retryCountRef.current + 1}/${maxRetries})...`]);
          retryCountRef.current++;
          
          // 重置连接状态并延迟重试
          connectingRef.current = false;
          setTimeout(connectWebSocket, retryDelay * retryCountRef.current);
        } else if (retryCountRef.current >= maxRetries) {
          console.error("Max retry attempts reached. Stopping reconnection attempts.");
          setProgressMessages(prev => [...prev, "❌ 已达到最大重试次数，停止重连。切换到轮询模式。"]);
          
          // 启用轮询作为备选方案
          setIsPolling(true);
          connectingRef.current = false;
        } else {
          // 如果任务不再进行中，则不尝试重连
          connectingRef.current = false;
        }
      };
    };
    
    // 辅助函数，用于清理WebSocket资源
    const cleanupWebSocket = () => {
      if (socket) {
        console.log("Closing existing WebSocket connection");
        socket.close();
        setSocket(null);
      }
      
      if (heartbeatInterval) {
        clearInterval(heartbeatInterval);
        heartbeatInterval = null;
      }
      
      if (connectionTimeout) {
        clearTimeout(connectionTimeout);
        connectionTimeout = null;
      }
    };

    // 只有在任务处于进行中状态时才尝试连接
    if (selectedTask?.status === 'In Progress') {
      console.log("Task is in progress, attempting WebSocket connection");
      retryCountRef.current = 0; // 重置重试计数
      connectWebSocket();
    } else {
      // 确保清理任何现有连接
      cleanupWebSocket();
    }

    // 清理函数
    return () => {
      cleanupWebSocket();
      connectingRef.current = false;
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
      checkPubSubStatus(); // 检查PubSub状态

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
    console.log("Submitting task with skip_download:", skipDownload);
    const taskPayload = {
      keyword,
      number,
      email,
      skip_download: skipDownload
    };
    console.log("Task payload:", taskPayload);
    
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
        console.log("Task created:", newTask);
        
        // 确保任务状态是 In Progress
        if (newTask.status !== 'In Progress') {
          console.warn("Task status is not In Progress:", newTask.status);
          // 强制设置状态为 In Progress
          newTask.status = 'In Progress';
        }
        
        // 1. 先重置进度消息
        setProgressMessages([]);
        
        // 2. 更新任务列表
        setTasks((prevTasks) => [...prevTasks, newTask]);
        
        // 3. 设置选中的任务
        setSelectedTask({ ...newTask, user_email: email });
        
        // 4. 启用轮询
        setIsPolling(true);
        
        // 5. 重置表单状态
        setShowModal(false);
        setKeyword("");
        setNumber(10);
        setSkipDownload(false);
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

  // 处理任务状态更新
  const handleTaskUpdate = (updatedTask: Task) => {
    console.log("Dashboard received task update:", updatedTask);
    
    // 更新任务列表中的任务
    setTasks(prevTasks => 
      prevTasks.map(task => 
        task.id === updatedTask.id ? updatedTask : task
      )
    );
    
    // 更新当前选中的任务
    setSelectedTask(updatedTask);
    
    // 如果任务已完成或失败，停止轮询
    if (updatedTask.status === 'Done' || updatedTask.status === 'Failed') {
      setIsPolling(false);
    }
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
          {pubsubEnabled !== null && (
            <div className={`mb-3 px-3 py-2 rounded text-center text-sm ${pubsubEnabled ? 'bg-green-600' : 'bg-red-600'}`}>
              PubSub状态: {pubsubEnabled ? '启用' : '禁用'}
            </div>
          )}
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