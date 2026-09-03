import { useState } from 'react';
import { Send } from 'lucide-react';
import { api } from '../services/api';
import type { FinanceQueryResponse } from '../types';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  data?: FinanceQueryResponse;
}

const suggestions = [
  'How many invoices above ₹10 lakh are awaiting approval?',
  'Which vendors have the highest rejection rate?',
  'Show me the total spending by vendor category',
  'What is the average processing time for invoices?',
  'How many duplicate invoices were detected?',
];

export default function FinanceAnalystPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const sendMessage = async (question: string) => {
    if (!question.trim()) return;
    const userMsg: ChatMessage = { role: 'user', content: question };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const resp = await api.queryFinance(question);
      const assistantMsg: ChatMessage = {
        role: 'assistant',
        content: resp.answer,
        data: resp,
      };
      setMessages(prev => [...prev, assistantMsg]);
    } catch (e) {
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: `Error: ${e instanceof Error ? e.message : 'Query failed'}` },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b bg-white">
        <h2 className="text-xl font-bold">Finance Analyst</h2>
        <p className="text-sm text-gray-500">Ask questions about your finance data</p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center mt-12">
            <p className="text-gray-400 mb-4">Try asking a question:</p>
            <div className="flex flex-wrap gap-2 justify-center max-w-xl mx-auto">
              {suggestions.map(s => (
                <button
                  key={s}
                  onClick={() => sendMessage(s)}
                  className="px-3 py-1.5 bg-white border rounded-full text-sm text-gray-600 hover:bg-blue-50 hover:border-blue-300 transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-2xl rounded-lg px-4 py-3 text-sm ${
              msg.role === 'user'
                ? 'bg-blue-600 text-white'
                : 'bg-white border shadow-sm'
            }`}>
              <p className="whitespace-pre-wrap">{msg.content}</p>

              {msg.data?.sql_query && (
                <div className="mt-3">
                  <span className="text-xs font-medium text-gray-500 block mb-1">Generated SQL:</span>
                  <pre className="bg-gray-900 text-green-400 rounded p-3 text-xs overflow-x-auto">
                    {msg.data.sql_query}
                  </pre>
                </div>
              )}

              {msg.data?.tools_used && msg.data.tools_used.length > 0 && (
                <div className="mt-2 flex gap-1 flex-wrap">
                  {msg.data.tools_used.map(t => (
                    <span key={t} className="px-2 py-0.5 bg-gray-100 rounded text-xs text-gray-600">{t}</span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-white border shadow-sm rounded-lg px-4 py-3 text-sm text-gray-400">
              Thinking...
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t bg-white p-4">
        <form
          onSubmit={e => { e.preventDefault(); sendMessage(input); }}
          className="flex gap-2 max-w-3xl mx-auto"
        >
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Ask about your finance data..."
            className="flex-1 border rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            <Send size={18} />
          </button>
        </form>
      </div>
    </div>
  );
}
