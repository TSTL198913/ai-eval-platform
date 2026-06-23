import React from 'react';
import { BookOpen, ExternalLink } from 'lucide-react';

const Docs: React.FC = () => {
  const docsUrl = '/docs';

  return (
    <div className="h-[calc(100vh-140px)] flex flex-col items-center justify-center p-8">
      <div className="text-center max-w-md">
        <div className="w-20 h-20 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-6">
          <BookOpen className="w-10 h-10 text-blue-600" />
        </div>
        <h2 className="text-2xl font-semibold text-gray-800 mb-2">API 文档</h2>
        <p className="text-gray-500 mb-8">FastAPI 自动生成的接口文档，支持在线调试</p>
        <div className="flex flex-col gap-4">
          <a
            href={docsUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center justify-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <ExternalLink className="w-5 h-5" />
            在新窗口打开 Swagger UI
          </a>
          <a
            href="/redoc"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center justify-center gap-2 px-6 py-3 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
          >
            <ExternalLink className="w-5 h-5" />
            在新窗口打开 ReDoc
          </a>
        </div>
        <div className="mt-8 p-4 bg-gray-50 rounded-lg">
          <p className="text-sm text-gray-400">
            提示：API 文档由后端自动生成，包含完整的接口定义和示例请求
          </p>
        </div>
      </div>
    </div>
  );
};

export default Docs;
