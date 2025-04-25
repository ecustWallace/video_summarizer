import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface Task {
  id?: number;
  keyword: string;
  video_number?: number;
  skip_download?: boolean;
  user_email?: string;
  status?: string;
  summary?: string | null;
  created_at?: string | null;
}

interface TaskPanelProps {
  task: Task;
  onBack: () => void;
  progressMessages: string[];
}

export default function TaskPanel({ task, onBack, progressMessages }: TaskPanelProps) {
  const [summary, setSummary] = useState<string | null>(task.summary || null);
  const [status, setStatus] = useState<string>(task.status || 'In Progress');
  const [loading, setLoading] = useState(task.status === 'In Progress');
  const [error, setError] = useState<string | null>(null);

  // 当任务属性更新时，更新本地状态
  useEffect(() => {
    if (task) {
      // 如果任务状态发生变化，立即更新本地状态
      if (task.status !== status) {
        setStatus(task.status || 'In Progress');
        setLoading(task.status === 'In Progress');
      }
      
      // 如果任务摘要发生变化，立即更新本地状态
      if (task.summary !== summary) {
        setSummary(task.summary || null);
      }
    }
  }, [task?.status, task?.summary, status, summary]);

  return (
    <div className="p-4">
      <motion.button
        onClick={onBack}
        className="text-blue-500 hover:text-blue-400 transition-colors duration-200 flex items-center mb-4"
        whileHover={{ x: -5 }}
        whileTap={{ scale: 0.95 }}
      >
        <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        Back to Task List
      </motion.button>

      {task ? (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
              {task.keyword}
            </h2>
            <div className="flex items-center space-x-4">
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                status === 'Done' ? 'bg-green-500 text-white' :
                status === 'Failed' ? 'bg-red-500 text-white' :
                'bg-yellow-500 text-white'
              }`}>
                {status}
              </span>
              {task.created_at && (
                <span className="text-gray-400 text-sm">
                  {new Date(task.created_at).toLocaleString()}
                </span>
              )}
            </div>
          </div>
          
          <AnimatePresence>
            {loading && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="bg-gray-900 rounded-lg p-4 mb-6 max-h-60 overflow-y-auto"
              >
                <div className="space-y-2">
                  {progressMessages.map((msg, idx) => (
                    <motion.div
                      key={idx}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.1 }}
                      className="text-sm text-gray-300"
                    >
                      {msg}
                    </motion.div>
                  ))}
                </div>
                <div className="mt-4 flex items-center text-blue-400">
                  <svg className="animate-spin h-5 w-5 mr-2" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Processing task...
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {error && !loading && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative mb-6"
              role="alert"
            >
              <strong className="font-bold">Error: </strong>
              <span className="block sm:inline">{error}</span>
            </motion.div>
          )}

          <AnimatePresence>
            {summary && !loading && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="bg-white rounded-lg shadow-xl overflow-hidden"
              >
                <div className="bg-gradient-to-r from-blue-500 to-purple-500 px-6 py-4">
                  <h3 className="text-xl font-semibold text-white flex items-center">
                    <svg className="w-6 h-6 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Final Summary
                  </h3>
                </div>
                <div className="p-6">
                  <div className="prose prose-lg max-w-none">
                    {summary.split('\n').map((paragraph, idx) => (
                      <motion.p
                        key={idx}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: idx * 0.1 }}
                        className="mb-4 text-gray-700 leading-relaxed"
                      >
                        {paragraph}
                      </motion.p>
                    ))}
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      ) : (
        <div className="text-center text-gray-500">No task selected or task data is missing.</div>
      )}
    </div>
  );
}