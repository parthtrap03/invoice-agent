import { useState, useCallback } from 'react';
import { Upload } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';

type UploadState = 'idle' | 'uploading' | 'done' | 'error';

const ACCEPTED = ['.pdf', '.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff'];

const SAMPLES = [
  { file: '01-clean-auto-approve.pdf', label: 'Clean invoice', outcome: 'Auto-approved' },
  { file: '02-po-variance-review.pdf', label: 'PO variance 2.22%', outcome: 'Review required' },
  { file: '03-wrong-gst-review.pdf', label: 'GST charged at 5%', outcome: 'Review required' },
  { file: '04-inactive-vendor-reject.pdf', label: 'Inactive vendor', outcome: 'Rejected' },
  { file: '05-duplicate-reject.pdf', label: 'Upload twice', outcome: 'Duplicate rejected' },
];

export default function UploadPage() {
  const navigate = useNavigate();
  const [state, setState] = useState<UploadState>('idle');
  const [error, setError] = useState('');
  const [resultId, setResultId] = useState('');
  const [dragOver, setDragOver] = useState(false);

  const handleFile = useCallback(async (file: File) => {
    const name = file.name.toLowerCase();
    if (!ACCEPTED.some(ext => name.endsWith(ext))) {
      setError('Accepted formats: PDF or image (PNG, JPG, JPEG, WEBP, BMP, TIFF)');
      setState('error');
      return;
    }
    setState('uploading');
    setError('');
    try {
      const result = await api.uploadInvoice(file);
      setResultId(result.id);
      setState('done');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed');
      setState('error');
    }
  }, []);

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const onFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  return (
    <div className="p-6 space-y-6 max-w-2xl mx-auto">
      <h2 className="text-2xl font-bold">Upload Invoice</h2>

      <div
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        className={`border-2 border-dashed rounded-lg p-12 text-center transition-colors ${
          dragOver ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'
        }`}
      >
        <Upload size={40} className="mx-auto text-gray-400 mb-4" />
        <p className="text-gray-600 mb-2">Drag & drop an invoice here (PDF or scanned image)</p>
        <p className="text-sm text-gray-400 mb-4">PDF, PNG, JPG, JPEG, WEBP, BMP, TIFF — or</p>
        <label className="inline-block px-4 py-2 bg-blue-600 text-white rounded-md cursor-pointer hover:bg-blue-700 transition-colors">
          Browse Files
          <input type="file" accept=".pdf,.png,.jpg,.jpeg,.webp,.bmp,.tiff,image/*" onChange={onFileSelect} className="hidden" />
        </label>
      </div>

      {state === 'uploading' && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-blue-700 text-sm">
          Uploading invoice...
        </div>
      )}

      {state === 'done' && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <p className="text-green-700 font-medium">✓ Invoice uploaded successfully</p>
          <button
            onClick={() => navigate(`/invoices/${resultId}`)}
            className="mt-2 text-sm text-blue-600 hover:underline"
          >
            View Invoice →
          </button>
        </div>
      )}

      {state === 'error' && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
          {error}
        </div>
      )}

      <section className="bg-white rounded-lg shadow-sm border p-5">
        <h3 className="font-semibold">Sample invoices</h3>
        <p className="text-sm text-gray-500 mt-1 mb-3">
          Each one exercises a different path through the rules engine. Download, then
          upload it back here and press Process.
        </p>
        <ul className="divide-y text-sm">
          {SAMPLES.map(s => (
            <li key={s.file} className="flex items-center justify-between py-2">
              <div>
                <a
                  href={`/demo-files/${s.file}`}
                  download
                  className="text-blue-600 hover:underline font-medium"
                >
                  {s.label}
                </a>
                <span className="text-gray-400 text-xs ml-2">{s.file}</span>
              </div>
              <span className="text-xs text-gray-500">{s.outcome}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
